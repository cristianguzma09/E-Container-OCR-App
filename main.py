from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Maritime Container OCR API",
    description="Backend service for detecting and reading maritime container IDs using AI/OCR.",
    version="1.0.0"
)

# Configure CORS for your future Angular frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Maritime Container OCR API!"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
