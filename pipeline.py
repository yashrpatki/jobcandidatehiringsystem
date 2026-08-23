import pytesseract
from pdf2image import convert_from_bytes, convert_from_path

from parser import parse_resume
from jd_processor import process_job_description
from ranker import rank_candidates



def extract_text_from_pdf(uploaded_file):
 
    try:
        # Check if input is a file path (str) or a Streamlit uploaded file object
        if isinstance(uploaded_file, str):
            images = convert_from_path(uploaded_file, dpi=300)
        else:
            file_bytes = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
            images = convert_from_bytes(file_bytes, dpi=300)

        ocr_text = ""
        for image in images:
            page_text = pytesseract.image_to_string(image)
            ocr_text += page_text + "\n"

        ocr_text = ocr_text.strip()

        if ocr_text:
            return ocr_text, "OCR"
            
    except Exception as e:
        raise RuntimeError(f"OCR text extraction failed: {e}")

    raise RuntimeError("No readable text could be extracted from the PDF using OCR.")



def process_resume(uploaded_file):
    text, method = extract_text_from_pdf(uploaded_file)
    parsed_data = parse_resume(text)

    # Safely retrieve filename regardless of object type
    filename = getattr(uploaded_file, "name", str(uploaded_file))

    return {
        "filename": filename,
        "resume_text": text,
        "extraction_method": method,
        "parsed_data": parsed_data,
    }



def process_candidates(role, job_description, uploaded_files):
    # 1. Process Job Description
    processed_jd, jd_error = None, None
    try:
        processed_jd = process_job_description(role=role, job_description=job_description)
    except Exception as e:
        jd_error = str(e)

    # 2. Parse Candidates via OCR
    candidates = []
    for file in uploaded_files:
        try:
            candidates.append(process_resume(file))
        except Exception as e:
            candidates.append({
                "filename": getattr(file, "name", str(file)),
                "resume_text": "",
                "extraction_method": "Failed",
                "parsed_data": {},
                "error": str(e)
            })

    # 3. Rank Candidates
    ranked_candidates, rank_error = [], None
    try:
        ranked_candidates = rank_candidates(
            candidates=candidates,
            job_description=processed_jd,
            role=role
        )
    except Exception as e:
        rank_error = str(e)

    return {
        "processed_jd": processed_jd,
        "processed_jd_error": jd_error,
        "candidates": candidates,
        "ranked_candidates": ranked_candidates,
        "ranked_candidates_error": rank_error
    }