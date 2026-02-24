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
    
    with patch("src.tools.docling_utils.extract_text_from_pdf", return_value=sample_text):
        text = doc_analyst.extract_text()
        assert isinstance(text, str)
        assert "Dialectical Synthesis" in text

def test_check_keywords(doc_analyst):
    """Test that check_keywords identifies important orchestration terms."""
    sample_text = "Dialectical Synthesis, Fan-In / Fan-Out, Metacognition"
    keywords = ["Dialectical Synthesis", "Fan-In / Fan-Out", "Metacognition", "State Synchronization"]
    
    with patch("src.tools.docling_utils.extract_text_from_pdf", return_value=sample_text):
        found_keywords = doc_analyst.check_keywords()
        # Should find all except "State Synchronization"
        assert "Dialectical Synthesis" in found_keywords
        assert "State Synchronization" not in found_keywords

def test_verify_file_paths(doc_analyst):
    """Test that verify_file_paths cross-checks PDF-referenced files."""
    sample_paths_in_pdf = ["src/tools/ast_parser.py", "src/tools/git_tools.py", "src/missing_file.py"]
    
    with patch("src.tools.docling_utils.extract_file_paths", return_value=sample_paths_in_pdf):
        with patch("src.tools.file_utils.read_file") as mock_read:
            # Simulate that only the first two files exist
            def side_effect(path):
                if path in ["src/tools/ast_parser.py", "src/tools/git_tools.py"]:
                    return "some content"
                else:
                    raise FileNotFoundError()
            mock_read.side_effect = side_effect
            
            verified_paths, hallucinated_paths = doc_analyst.verify_file_paths()
            assert "src/tools/ast_parser.py" in verified_paths
            assert "src/missing_file.py" in hallucinated_paths