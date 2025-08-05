# google_ai_service.py

import os
import json
import logging
import google.generativeai as genai
from prompts import ANALYSIS_PROMPT

# Load Google AI credentials
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.5-pro")
MAX_RETRIES = 3

# Configure Google AI
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(GOOGLE_MODEL)
else:
    model = None
    logging.warning("Google API key not found. Set GOOGLE_API_KEY environment variable.")

async def analyze_document(text: str) -> dict:
    """
    Analyzes the document using Google's Generative AI with retries.
    This single call handles classification and data extraction.
    """
    logging.info("Starting unified document analysis with Google AI...")
    
    if not model:
        logging.error("Google AI model not configured. Please set GOOGLE_API_KEY.")
        return _get_fallback_response("Google AI not configured")
    
    # Use full text for analysis, but consider truncating for very large docs if needed
    content_to_send = text

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"Attempt {attempt}: Sending analysis request to Google AI...")
            
            # Create the prompt for Google AI
            prompt = f"{ANALYSIS_PROMPT}\n\nDocument text to analyze:\n{content_to_send}"
            
            response = model.generate_content(prompt)
            
            if response.text:
                content = response.text.strip()
                # Try to extract JSON from the response
                try:
                    # Look for JSON in the response
                    start_idx = content.find('{')
                    end_idx = content.rfind('}') + 1
                    if start_idx != -1 and end_idx != 0:
                        json_content = content[start_idx:end_idx]
                        result = json.loads(json_content)
                    else:
                        # If no JSON found, try to parse the entire response
                        result = json.loads(content)
                    
                    if isinstance(result, dict):
                        # Ensure we have the required fields
                        if 'document_type' not in result:
                            result['document_type'] = 'Document'
                        if 'summary' not in result:
                            result['summary'] = 'Document analyzed successfully'
                        if 'key_information' not in result:
                            result['key_information'] = {}
                        if 'extracted_data' not in result:
                            result['extracted_data'] = {}
                        
                        logging.info("Successfully analyzed document with Google AI.")
                        return result
                    else:
                        logging.warning(f"Attempt {attempt}: Unexpected analysis JSON format. Result: {result}")
                        # Continue to retry if format is wrong
                        
                except json.JSONDecodeError as e:
                    logging.warning(f"Attempt {attempt} failed with JSON decode error: {e}. Response: {content}")
                    # Try to create a structured response from the text
                    if attempt == MAX_RETRIES:
                        return _create_structured_response_from_text(content)
            else:
                logging.warning(f"Attempt {attempt}: Empty response from Google AI")

        except Exception as e:
            logging.warning(f"Attempt {attempt} failed with API error: {e}")
            
            # Handle rate limiting specifically
            if "429" in str(e) or "quota" in str(e).lower():
                logging.warning("Rate limit exceeded. Consider waiting or upgrading your plan.")
                if attempt == MAX_RETRIES:
                    return _get_fallback_response("Rate limit exceeded. Please try again later or upgrade your Google AI plan.")
            
            if attempt == MAX_RETRIES:
                logging.error("All analysis attempts failed.")
                return _get_fallback_response(f"Analysis completed with limited information after {MAX_RETRIES} retries: {str(e)}")

    # Fallback response if all retries fail to produce a valid dict
    logging.error("All analysis attempts failed to produce a valid result.")
    return _get_fallback_response("Analysis completed with fallback method")

def _create_structured_response_from_text(text: str) -> dict:
    """
    Creates a structured response from plain text when JSON parsing fails.
    """
    return {
        "language": "Unknown",
        "document_type": "Document",
        "summary": text[:500] + "..." if len(text) > 500 else text,
        "key_information": {
            "important_details": ["Document processed with text analysis"],
            "dates": [],
            "amounts": [],
            "names": [],
            "actions_required": []
        },
        "extracted_data": {
            "raw_analysis": text
        },
        "error": "JSON parsing failed, using text analysis"
    }

def _get_fallback_response(error_message: str) -> dict:
    """
    Returns a fallback response when analysis fails.
    """
    return {
        "language": "Unknown",
        "document_type": "Document",
        "summary": "Document analysis completed with limited information due to API errors.",
        "key_information": {
            "important_details": ["Document processed with limited analysis"],
            "dates": [],
            "amounts": [],
            "names": [],
            "actions_required": []
        },
        "extracted_data": {},
        "error": error_message
    } 