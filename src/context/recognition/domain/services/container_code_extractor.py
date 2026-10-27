"""Find container numbers in raw OCR output.

This is the heart of the recognition context. Everything an OCR engine returns
is noise until something decides which parts of it look like an ISO 6346 mark,
and the check digit is what makes that decision cheap and reliable: it is
arithmetic over the other ten characters, so a read that satisfies it is
almost certainly correct.

That same arithmetic also lets a near-miss be repaired. OCR confuses a small,
well-known set of character pairs on weathered paint - ``0`` for ``O``, ``1``
for ``I``, ``5`` for ``S``, ``8`` for ``B``. Trying those substitutions one at
a time and keeping only the ones that make the check digit come out right
turns a large share of failed reads into good ones, without ever inventing a
number: a repair that does not satisfy the check digit is discarded.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from src.context.recognition.domain.model.container_code_candidate import (
    ContainerCodeCandidate,
)
from src.context.recognition.domain.model.confidence import Confidence
from src.context.recognition.domain.model.text_fragment import TextFragment
from src.shared_kernel.iso6346 import (
    BODY_LENGTH,
    BODY_PATTERN,
    NUMBER_LENGTH,
    NUMBER_PATTERN,
    calculate_check_digit,
)

#: In the first four characters a letter is expected, so digits are suspect.
_TO_LETTER = {"0": "O", "1": "I", "2": "Z", "4": "A", "5": "S", "6": "G", "8": "B"}

#: In the last seven a digit is expected, so letters are suspect.
_TO_DIGIT = {
    "O": "0", "Q": "0", "D": "0",
    "I": "1", "L": "1",
    "Z": "2",
    "A": "4",
    "S": "5",
    "G": "6",
    "T": "7",
    "B": "8",
}

#: How many neighbouring fragments to try joining. A number painted across
#: three lines - prefix, serial, check digit - is the common case.
_MAX_JOIN = 3


@dataclass(frozen=True)
class _Window:
    text: str
    confidence: float
    box: object | None
    raw: str
    #: True when this is a 10-character body whose check digit was never read,
    #: rather than a complete 11-character number.
    body_only: bool = False


class ContainerCodeExtractor:
    """Turns OCR fragments into ranked container-number candidates."""

    def extract(
        self, fragments: Sequence[TextFragment]
    ) -> list[ContainerCodeCandidate]:
        """Return every plausible reading, best first.

        An empty list means nothing in the image looked like a container
        number - an ordinary outcome for a blurred or badly framed photo.
        """
        candidates: dict[str, ContainerCodeCandidate] = {}

        for window in self._windows(fragments):
            for candidate in self._interpret(window):
                existing = candidates.get(candidate.value)
                if existing is None or self._preferred(candidate, existing):
                    candidates[candidate.value] = candidate

        return sorted(candidates.values(), key=lambda c: c.score, reverse=True)

    @staticmethod
    def _preferred(
        new: ContainerCodeCandidate, current: ContainerCodeCandidate
    ) -> bool:
        """Break a tie between two readings of the same number.

        The same number is often found twice - once inside a single fragment
        and again inside that fragment joined to its neighbours. They score
        identically, so the tighter source text wins: a reviewer is better
        served by ``C5QU3054383`` than by ``MAERSK C5QU3054383``.
        """
        if new.score != current.score:
            return new.score > current.score
        return len(new.raw_text) < len(current.raw_text)

    # -- scanning ----------------------------------------------------------
    def _windows(self, fragments: Sequence[TextFragment]) -> Iterable[_Window]:
        """Every stretch of text worth examining.

        Fragments are tried alone and joined with their neighbours, because a
        container number is usually painted on more than one line and comes
        back from the engine already split apart.

        Two rules stop that joining from inventing numbers out of unrelated
        markings:

        * A window may only **start** where a fragment starts. Without it, a
          window can begin mid-word: the weights panel on a real container
          turns ``PAYLOAD 27.400 60.410`` into ``OADZ7400604``, which happens
          to satisfy the check digit and then outranks the real number.
          Container numbers do not begin in the middle of a word.
        * A ten-character body that **ends** exactly where a fragment ends is
          also offered on its own. On most containers the check digit is
          painted in its own box, and detectors routinely miss it - so the
          real reading arrives one character short.
        """
        usable = [f for f in fragments if not f.is_empty]

        for start in range(len(usable)):
            for length in range(1, _MAX_JOIN + 1):
                group = usable[start : start + length]
                if len(group) < length:
                    break

                cleaned = [self._clean(f.text) for f in group]
                joined = "".join(cleaned)
                if len(joined) < BODY_LENGTH:
                    continue

                # Offsets where a fragment begins, plus the very end.
                edges: list[int] = []
                position = 0
                for piece in cleaned:
                    edges.append(position)
                    position += len(piece)
                edges.append(position)
                boundaries = set(edges)

                # The weakest fragment in the group caps the confidence.
                confidence = min(f.confidence.value for f in group)
                box = group[0].box if len(group) == 1 else None
                raw = " ".join(f.text for f in group)

                for offset in edges:
                    if offset + NUMBER_LENGTH <= len(joined):
                        yield _Window(
                            text=joined[offset : offset + NUMBER_LENGTH],
                            confidence=confidence,
                            box=box,
                            raw=raw,
                        )

                    end = offset + BODY_LENGTH
                    if end <= len(joined) and end in boundaries:
                        yield _Window(
                            text=joined[offset:end],
                            confidence=confidence,
                            box=box,
                            raw=raw,
                            body_only=True,
                        )

    @staticmethod
    def _clean(text: str) -> str:
        return "".join(ch for ch in text.upper() if ch.isalnum())

    # -- interpreting ------------------------------------------------------
    def _interpret(self, window: _Window) -> list[ContainerCodeCandidate]:
        if window.body_only:
            return self._interpret_body(window)

        coerced, coerced_by_shape = self._coerce(window.text)
        if not NUMBER_PATTERN.fullmatch(coerced):
            return []

        expected = calculate_check_digit(coerced[0:3], coerced[3], coerced[4:10])
        read_digit = int(coerced[10])

        if expected == read_digit:
            return [
                self._candidate(
                    window,
                    value=coerced,
                    valid=True,
                    expected=expected,
                    repaired=coerced_by_shape,
                )
            ]

        results = [
            self._candidate(
                window,
                value=coerced,
                valid=False,
                expected=expected,
                repaired=coerced_by_shape,
            )
        ]
        repaired = self._repair(coerced)
        if repaired is not None:
            results.append(
                self._candidate(
                    window,
                    value=repaired,
                    valid=True,
                    expected=int(repaired[10]),
                    repaired=True,
                )
            )
        return results

    def _interpret_body(self, window: _Window) -> list[ContainerCodeCandidate]:
        """Complete a reading whose check digit was never captured.

        This is not the same as recomputing a check digit that *was* read and
        disagreed - that would destroy the only independent check there is,
        and is refused elsewhere. Here the character was never seen at all, so
        arithmetic is the only thing that can supply it. The result is marked
        ``check_digit_inferred`` and always goes to a person.
        """
        coerced, changed = self._coerce(window.text, BODY_LENGTH)
        if not BODY_PATTERN.fullmatch(coerced):
            return []

        check_digit = calculate_check_digit(
            coerced[0:3], coerced[3], coerced[4:BODY_LENGTH]
        )
        return [
            self._candidate(
                window,
                value=f"{coerced}{check_digit}",
                valid=True,
                expected=check_digit,
                repaired=changed,
                inferred=True,
            )
        ]

    @staticmethod
    def _coerce(window: str, length: int = NUMBER_LENGTH) -> tuple[str, bool]:
        """Push each character towards the shape its position demands."""
        chars = list(window)
        changed = False

        for index in range(4):
            replacement = _TO_LETTER.get(chars[index])
            if replacement is not None:
                chars[index] = replacement
                changed = True

        for index in range(4, length):
            replacement = _TO_DIGIT.get(chars[index])
            if replacement is not None:
                chars[index] = replacement
                changed = True

        return "".join(chars), changed

    @staticmethod
    def _repair(number: str) -> str | None:
        """Try one character substitution in the body; keep it only if it works.

        Only substitutions from the known confusion table are attempted, and
        only a result whose check digit is correct is returned - so this can
        correct a misread character but can never fabricate a number.
        """
        for index in range(BODY_LENGTH):
            current = number[index]
            alternatives = (
                [letter for digit, letter in _TO_LETTER.items() if digit == current]
                + [d for letter, d in _TO_DIGIT.items() if letter == current]
                + ([_TO_LETTER[current]] if current in _TO_LETTER else [])
                + ([_TO_DIGIT[current]] if current in _TO_DIGIT else [])
            )
            for alternative in dict.fromkeys(alternatives):
                attempt = number[:index] + alternative + number[index + 1 :]
                if not NUMBER_PATTERN.fullmatch(attempt):
                    continue
                expected = calculate_check_digit(
                    attempt[0:3], attempt[3], attempt[4:10]
                )
                if expected == int(attempt[10]):
                    return attempt
        return None

    @staticmethod
    def _candidate(
        window: _Window,
        *,
        value: str,
        valid: bool,
        expected: int,
        repaired: bool,
        inferred: bool = False,
    ) -> ContainerCodeCandidate:
        return ContainerCodeCandidate(
            raw_text=window.raw,
            value=value,
            confidence=Confidence(window.confidence),
            check_digit_valid=valid,
            expected_check_digit=expected,
            repaired=repaired,
            check_digit_inferred=inferred,
            box=window.box,  # type: ignore[arg-type]
        )
