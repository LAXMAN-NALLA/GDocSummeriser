# textract_service.py

import os
import logging
import boto3
import pdfplumber
import pandas as pd
from docx import Document
from io import BytesIO
from botocore.exceptions import ClientError
import asyncio
from pathlib import Path

# Initialize AWS Textract client conditionally
# Only initialize if AWS credentials are available
textract_client = None
aws_available = False

try:
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION")
    
    if aws_access_key and aws_secret_key and aws_region:
        textract_client = boto3.client(
            "textract",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region
        )
        aws_available = True
        logging.info("AWS Textract client initialized successfully")
    else:
        logging.warning("AWS credentials not found. Textract OCR will not be available.")
        logging.info("To enable AWS Textract, set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_REGION environment variables")
except Exception as e:
    logging.warning(f"Failed to initialize AWS Textract client: {e}")
    textract_client = None
    aws_available = False

# --- Synchronous blocking functions ---
# These functions perform the actual file processing and are designed
# to be run in a separate thread to avoid blocking the server.

def _extract_pdf_sync(file_path):
    """Extracts text from a digital PDF."""
    with pdfplumber.open(file_path) as pdf:
        return "".join(page.extract_text() or "" for page in pdf.pages)

def _extract_docx_sync(file_path):
    """Extracts text from a .docx file."""
    doc = Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])

def _extract_table_sync(file_path, is_csv):
    """Extracts text from a .csv or .xlsx file."""
    df = pd.read_csv(file_path) if is_csv else pd.read_excel(file_path)
    return df.to_string(index=False)

def _extract_txt_sync(file_path):
    """Extracts text from a plain .txt file."""
    # Use 'errors=ignore' to handle potential encoding issues gracefully
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

def _textract_sync(file_bytes):
    """Performs OCR using AWS Textract for images or scanned documents."""
    if not aws_available or textract_client is None:
        raise Exception("AWS Textract is not available. Please configure AWS credentials.")
    response = textract_client.detect_document_text(Document={"Bytes": file_bytes})
    return "\n".join([block['Text'] for block in response['Blocks'] if block['BlockType'] == 'LINE'])

# --- Main async function ---
# This is the single entry point called by your main application.

async def extract_text_from_upload(file_path: str, file_bytes: bytes) -> str:
    """
    Extracts text from various file types. It tries native libraries first
    for efficiency and falls back to AWS Textract for images and scanned documents.
    All blocking I/O is run in a separate thread.
    """
    ext = Path(file_path).suffix.lower()
    full_text = ""

    try:
        # Step 1: Attempt extraction with efficient, native libraries
        if ext == ".pdf":
            full_text = await asyncio.to_thread(_extract_pdf_sync, file_path)
        elif ext == ".docx":
            full_text = await asyncio.to_thread(_extract_docx_sync, file_path)
        elif ext in [".csv", ".xlsx"]:
            full_text = await asyncio.to_thread(_extract_table_sync, file_path, is_csv=(ext == ".csv"))
        elif ext == ".txt":
            full_text = await asyncio.to_thread(_extract_txt_sync, file_path)

        # If text was successfully extracted, return it immediately.
        if full_text and full_text.strip():
            logging.info(f"Successfully extracted text from {ext} using native library.")
            return full_text.strip()

        # Step 2: Fallback to AWS Textract for images, scanned PDFs, or failed extractions
        if aws_available:
            logging.info(f"Falling back to AWS Textract for {file_path}")
            return await asyncio.to_thread(_textract_sync, file_bytes)
        else:
            logging.warning(f"AWS Textract not available. Cannot process {file_path} as image/OCR document.")
            return ""

    except Exception as e:
        # If any primary extraction method fails, log the error and try a final fallback to Textract.
        logging.error(f"Error during text extraction for {file_path}: {e}. Attempting Textract as final fallback.", exc_info=True)
        try:
            if aws_available:
                return await asyncio.to_thread(_textract_sync, file_bytes)
            else:
                logging.warning("AWS Textract not available for fallback processing.")
                return ""
        except ClientError as ce:
            logging.error(f"AWS Textract API error: {ce}")
            return ""
        except Exception as te:
            logging.error(f"Textract fallback error: {te}")
            return ""
