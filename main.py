# main.py

import os
import tempfile
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file at the very beginning
load_dotenv()

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import textract_service
import google_ai_service

app = FastAPI(title="Document Analysis API")
logging.basicConfig(level=logging.INFO)

# Configure CORS for development (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Allowed file extensions
ALLOWED_EXTENSIONS = [".pdf", ".docx", ".csv", ".xlsx", ".png", ".jpg", ".jpeg", ".txt"]

def validate_file(file: UploadFile):
    """Validates the uploaded file extension."""
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

def infer_document_type_from_content(text: str) -> str:
    """
    Intelligently infers document type from content using keyword analysis.
    """
    text_lower = text.lower()
    
    # Financial documents
    if any(word in text_lower for word in ['invoice', 'bill', 'payment', 'amount due', 'total']):
        return "Invoice"
    elif any(word in text_lower for word in ['balance sheet', 'assets', 'liabilities', 'equity']):
        return "Balance Sheet"
    elif any(word in text_lower for word in ['profit', 'loss', 'revenue', 'income statement']):
        return "Profit & Loss Statement"
    elif any(word in text_lower for word in ['receipt', 'purchase', 'transaction']):
        return "Receipt"
    
    # Legal documents
    elif any(word in text_lower for word in ['contract', 'agreement', 'terms', 'clause', 'party']):
        return "Contract"
    elif any(word in text_lower for word in ['legal', 'attorney', 'lawyer', 'court']):
        return "Legal Document"
    
    # Business documents
    elif any(word in text_lower for word in ['report', 'analysis', 'findings', 'conclusion']):
        return "Report"
    elif any(word in text_lower for word in ['proposal', 'offer', 'quote', 'estimate']):
        return "Proposal"
    elif any(word in text_lower for word in ['memo', 'memorandum', 'internal']):
        return "Memo"
    elif any(word in text_lower for word in ['policy', 'procedure', 'guideline']):
        return "Policy Document"
    
    # Personal documents
    elif any(word in text_lower for word in ['resume', 'cv', 'curriculum vitae', 'experience', 'skills']):
        return "Resume"
    elif any(word in text_lower for word in ['letter', 'dear', 'sincerely', 'yours truly']):
        return "Letter"
    elif any(word in text_lower for word in ['certificate', 'certification', 'award']):
        return "Certificate"
    
    # Technical documents
    elif any(word in text_lower for word in ['manual', 'guide', 'instruction', 'how to']):
        return "Manual"
    elif any(word in text_lower for word in ['specification', 'technical', 'specs']):
        return "Technical Document"
    
    # Academic documents
    elif any(word in text_lower for word in ['research', 'study', 'academic', 'university']):
        return "Academic Document"
    
    # Government documents
    elif any(word in text_lower for word in ['government', 'official', 'department', 'ministry']):
        return "Government Document"
    
    # Medical documents
    elif any(word in text_lower for word in ['medical', 'health', 'patient', 'diagnosis', 'treatment']):
        return "Medical Document"
    
    # If no specific type is detected, return a descriptive type based on content length
    if len(text) < 100:
        return "Short Document"
    elif len(text) < 1000:
        return "Medium Document"
    else:
        return "Long Document"

@app.get("/health", status_code=200)
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    """Main endpoint to upload and analyze a document."""
    tmp_path = None
    try:
        validate_file(file)

        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            file_bytes = await file.read()
            tmp.write(file_bytes)
            tmp_path = tmp.name

        extracted_text = await textract_service.extract_text_from_upload(tmp_path, file_bytes)
        if not extracted_text or not extracted_text.strip():
            raise HTTPException(status_code=422, detail="Failed to extract text from document.")

        # Analyze the document content
        analysis_result = await google_ai_service.analyze_document(extracted_text)
        
        # Ensure we have a valid result structure
        if not isinstance(analysis_result, dict):
            analysis_result = {
                "document_type": "Document",
                "summary": "Document analysis completed",
                "extracted_data": {},
                "analysis_output": str(analysis_result)
            }
        
        # Get document type, defaulting to a meaningful type
        doc_type = analysis_result.get("document_type", "Document")
        
        # If the document type is too generic, try to infer from content
        if doc_type in ["GeneralDocument", "Document", "Unknown"]:
            doc_type = infer_document_type_from_content(extracted_text)
            analysis_result["document_type"] = doc_type

        logging.info(f"Analysis successful for {file.filename}. Type: {doc_type}")

        return {
            "filename": file.filename,
            "document_type": doc_type,
            "analysis": analysis_result
        }

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logging.error(f"An error occurred in the /analyze endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal server error occurred during analysis.")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
