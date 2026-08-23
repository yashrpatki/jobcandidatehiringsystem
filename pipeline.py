import pytesseract
from pdf2image import convert_from_bytes, convert_from_path
from pypdf import PdfReader
import io

from parser import parse_resume
from jd_processor import process_job_description
from ranker import rank_candidates


MIN_TEXT_LENGTH = 50  # below this, treat the PDF as image-only and fall back to OCR


def _get_pdf_bytes(uploaded_file):
    if isinstance(uploaded_file, str):
        with open(uploaded_file, "rb") as f:
            return f.read()
    return uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()


def extract_text_direct(pdf_bytes):
    """Fast path: read the PDF's existing text layer. No image conversion, no OCR."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text += page_text + "\n"
        return text.strip()
    except Exception:
        return ""


def extract_text_ocr(uploaded_file):
    """Slow path: rasterize pages and run tesseract. Only used when there's no text layer."""
    try:
        if isinstance(uploaded_file, str):
            images = convert_from_path(uploaded_file, dpi=200)
        else:
            file_bytes = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
            images = convert_from_bytes(file_bytes, dpi=200)

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


def extract_text_from_pdf(uploaded_file):
    pdf_bytes = _get_pdf_bytes(uploaded_file)

    direct_text = extract_text_direct(pdf_bytes)
    if len(direct_text) >= MIN_TEXT_LENGTH:
        return direct_text, "text"

    # No usable text layer (likely a scanned resume) — fall back to OCR
    return extract_text_ocr(io.BytesIO(pdf_bytes))



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
