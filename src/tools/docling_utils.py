"""
docling_utils.py — Chunked, queryable PDF interface for the DocAnalyst detective.

Design rationale
----------------
The previous implementation extracted a single giant text blob from the entire
PDF and handed it to detectives in one shot.  That approach has two problems:

1. **Context window overflow** — Large PDFs easily exceed LLM context limits.
2. **Low query precision** — Detectives had no way to ask "what does page 3 say
   about StateGraph?" without scanning the entire document.

This module replaces that approach with a ``ForensicPDFReader`` class that:

* Splits the PDF into **page-level chunks** (each chunk is an independent unit
  of evidence with its own page number).
* Exposes a ``query(keyword)`` method so detectives can ask targeted questions
  and receive only the relevant chunks — not the whole document.
* Provides a ``keyword_summary()`` method that returns per-keyword hit counts
  and surrounding context sentences, suitable for inserting directly into a
  forensic evidence description.

The legacy ``extract_text_from_pdf`` and ``find_keywords_in_text`` functions are
kept for backwards compatibility with any existing callers.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

try:
    from pypdf import PdfReader
    _PYPDF_AVAILABLE = True
except ImportError:
    _PYPDF_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data model for a single PDF chunk
# ---------------------------------------------------------------------------

@dataclass
class PDFChunk:
    """
    Represents a single page extracted from a PDF document.

    Attributes
    ----------
    page_number : int
        1-based page index within the source PDF.
    text        : str
        Full text content of this page (whitespace-normalised).
    source_path : str
        Absolute path to the PDF file this chunk was extracted from.
    """
    page_number: int
    text: str
    source_path: str

    def sentences(self) -> List[str]:
        """Split the page text into sentences (split on '.' or newlines)."""
        raw = re.split(r"(?<=[.!?])\s+|\n{2,}", self.text)
        return [s.strip() for s in raw if s.strip()]

    def contains(self, keyword: str, case_sensitive: bool = False) -> bool:
        """Return True if *keyword* appears anywhere in this chunk's text."""
        haystack = self.text if case_sensitive else self.text.lower()
        needle = keyword if case_sensitive else keyword.lower()
        return needle in haystack

    def matching_sentences(self, keyword: str, case_sensitive: bool = False) -> List[str]:
        """Return only the sentences within this chunk that contain *keyword*."""
        return [
            s for s in self.sentences()
            if keyword.lower() in s.lower() or (case_sensitive and keyword in s)
        ]


# ---------------------------------------------------------------------------
# ForensicPDFReader — the main chunked, queryable interface
# ---------------------------------------------------------------------------

class ForensicPDFReader:
    """
    A chunked, queryable PDF reader designed for detective forensic analysis.

    Usage
    -----
    >>> reader = ForensicPDFReader("report/audit_submission.pdf")
    >>> reader.load()
    >>> hits = reader.query("StateGraph")
    >>> for chunk in hits:
    ...     print(f"Page {chunk.page_number}: {chunk.matching_sentences('StateGraph')}")

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file to analyse.
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = str(Path(pdf_path).resolve())
        self.chunks: List[PDFChunk] = []
        self._loaded = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self) -> "ForensicPDFReader":
        """
        Read the PDF or Markdown file and split it into per-page (PDF) 
        or per-section (Markdown) ``PDFChunk`` objects.
        """
        path = Path(self.pdf_path)
        if not path.exists():
            raise FileNotFoundError(
                f"[DocAnalyst] File not found at '{self.pdf_path}'."
            )

        self.chunks = []
        
        # Handle Markdown files
        if path.suffix.lower() == ".md":
            try:
                with open(path, "r", encoding="utf-8") as f:
                    full_text = f.read()
                # Split by H2 headers for "page-like" chunking
                sections = re.split(r"\n## ", full_text)
                for i, section in enumerate(sections, start=1):
                    normalised = re.sub(r"[ \t]+", " ", section).strip()
                    if normalised:
                        self.chunks.append(
                            PDFChunk(page_number=i, text=normalised, source_path=self.pdf_path)
                        )
                self._loaded = True
                return self
            except Exception as exc:
                raise RuntimeError(f"[DocAnalyst] Failed to read Markdown '{self.pdf_path}': {exc}")

        # Handle PDF files
        if not _PYPDF_AVAILABLE:
            raise RuntimeError(
                "[DocAnalyst] 'pypdf' is not installed. "
                "Run `pip install pypdf` to enable PDF forensic analysis."
            )

        try:
            reader = PdfReader(str(path))
        except Exception as exc:
            raise RuntimeError(
                f"[DocAnalyst] Failed to open '{self.pdf_path}' as a PDF: {exc}"
            ) from exc

        for page_index, page in enumerate(reader.pages, start=1):
            try:
                raw_text = page.extract_text() or ""
            except Exception:
                raw_text = ""
            normalised = re.sub(r"[ \t]+", " ", raw_text).strip()
            self.chunks.append(
                PDFChunk(page_number=page_index, text=normalised, source_path=self.pdf_path)
            )

        self._loaded = True
        return self

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            raise RuntimeError(
                "[ForensicPDFReader] Call .load() before querying."
            )

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def query(self, keyword: str, case_sensitive: bool = False) -> List[PDFChunk]:
        """
        Return only the pages that contain *keyword*.

        This is the core "targeted question" interface — detectives ask about
        a specific term and receive only the relevant pages, not the whole document.

        Parameters
        ----------
        keyword        : str  — The term to search for.
        case_sensitive : bool — Default False (case-insensitive search).

        Returns
        -------
        List[PDFChunk]
            Ordered list of pages (by page number) that contain the keyword.
        """
        self._ensure_loaded()
        return [c for c in self.chunks if c.contains(keyword, case_sensitive)]

    def query_multi(self, keywords: List[str]) -> Dict[str, List[PDFChunk]]:
        """
        Run :meth:`query` for each keyword and return a mapping.

        Parameters
        ----------
        keywords : List[str]
            List of terms to search for simultaneously.

        Returns
        -------
        Dict[str, List[PDFChunk]]
            ``{keyword: [matching pages]}`` for every keyword.
        """
        self._ensure_loaded()
        return {kw: self.query(kw) for kw in keywords}

    def full_text(self) -> str:
        """
        Return the entire PDF as one concatenated string (legacy fallback).

        Prefer :meth:`query` for forensic analysis; use this only when you
        need the raw dump for heuristic scanning.
        """
        self._ensure_loaded()
        return "\n\n".join(
            f"[Page {c.page_number}]\n{c.text}" for c in self.chunks
        )

    def keyword_summary(self, keywords: List[str]) -> Dict[str, dict]:
        """
        Produce a structured forensic summary for a list of keywords.

        Returns a dict keyed by keyword, each value containing:
        - ``hit_count``   : number of pages where the keyword appears.
        - ``page_numbers``: list of matching page numbers.
        - ``contexts``    : list of matching sentences (up to 3 per page).

        This summary is suitable for direct insertion into an ``Evidence``
        description field.
        """
        self._ensure_loaded()
        summary: Dict[str, dict] = {}
        for kw in keywords:
            matching = self.query(kw)
            contexts: List[str] = []
            for chunk in matching:
                contexts.extend(chunk.matching_sentences(kw)[:3])
            summary[kw] = {
                "hit_count": len(matching),
                "page_numbers": [c.page_number for c in matching],
                "contexts": contexts[:10],  # cap at 10 total to stay concise
            }
        return summary


# ---------------------------------------------------------------------------
# Legacy API — kept for backward compatibility
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract all text from a PDF as a single string.

    .. deprecated::
        Use ``ForensicPDFReader(pdf_path).load().full_text()`` instead for
        chunked, queryable access.

    Raises
    ------
    FileNotFoundError
        If the PDF file does not exist.
    RuntimeError
        If pypdf is not available.
    """
    return ForensicPDFReader(pdf_path).load().full_text()


def find_keywords_in_text(text: str, keywords: List[str]) -> Dict[str, List[str]]:
    """
    Return sentences from *text* that contain each keyword.

    .. deprecated::
        Use ``ForensicPDFReader(pdf_path).load().keyword_summary(keywords)``
        for a richer, page-aware result.
    """
    results: Dict[str, List[str]] = {kw: [] for kw in keywords}
    sentences = re.split(r"(?<=[.!?])\s+|\n", text)
    for sentence in sentences:
        s = sentence.strip()
        if not s:
            continue
        for kw in keywords:
            if kw.lower() in s.lower():
                results[kw].append(s)
    return results