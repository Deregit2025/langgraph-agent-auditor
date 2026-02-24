# tests/test_docanalyst.py
import pytest
from unittest.mock import patch, MagicMock
from src.nodes.detectives import DocAnalyst

SAMPLE_PDF_PATH = "audit/report_example.pdf"

@pytest.fixture
def doc_analyst():
    """Create a DocAnalyst instance for testing."""
    return DocAnalyst(pdf_path=SAMPLE_PDF_PATH)

def test_extract_text(doc_analyst):
    """Test that extract_text returns PDF text."""
    sample_text = "Dialectical Synthesis, Fan-In / Fan-Out, Metacognition"
    
    with patch("src.nodes.detectives.extract_text_from_pdf", return_value=sample_text):
        text = doc_analyst.extract_text()
        assert isinstance(text, str)
        assert "Dialectical Synthesis" in text

def test_check_keywords(doc_analyst):
    """Test that check_keywords identifies important orchestration terms."""
    sample_text = "Dialectical Synthesis, Fan-In / Fan-Out, Metacognition"
    keywords = ["Dialectical Synthesis", "Fan-In / Fan-Out", "Metacognition", "State Synchronization"]
    
    with patch("src.nodes.detectives.extract_text_from_pdf", return_value=sample_text):
        found_keywords = doc_analyst.check_keywords(keywords)
        # Should find all except "State Synchronization"
        assert "Dialectical Synthesis" in found_keywords
        assert len(found_keywords["Dialectical Synthesis"]) > 0
        assert "State Synchronization" in found_keywords
        assert len(found_keywords["State Synchronization"]) == 0

def test_verify_file_paths(doc_analyst):
    """Test that verify_file_paths cross-checks PDF-referenced files."""
    # My dummy implementation returns ([], [])
    verified_paths, hallucinated_paths = doc_analyst.verify_file_paths()
    assert isinstance(verified_paths, list)
    assert isinstance(hallucinated_paths, list)
