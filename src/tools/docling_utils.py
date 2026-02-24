# src/tools/docling_utils.py

from pathlib import Path
from pypdf import PdfReader
from typing import List, Dict

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extracts text from a PDF file.
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    reader = PdfReader(str(pdf_file))
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def find_keywords_in_text(text: str, keywords: List[str]) -> Dict[str, List[str]]:
    """
    Returns a dictionary with each keyword and the sentences containing it.
    """
    results = {keyword: [] for keyword in keywords}
    sentences = text.split(".")
    for sentence in sentences:
        for keyword in keywords:
            if keyword.lower() in sentence.lower():
                results[keyword].append(sentence.strip())
    return results