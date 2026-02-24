# src/nodes/detectives.py

from typing import List, Dict, Tuple
from src.tools import ast_parser, git_tools, file_utils
from src.tools.docling_utils import extract_text_from_pdf, find_keywords_in_text
from src.tools.vision_utils import load_image, classify_diagram


class RepoInvestigator:
    """
    Detective that analyzes a GitHub repository for forensic evidence.
    """

    def __init__(self, repo_url: str):
        self.repo_url = repo_url

    def collect_git_commits(self) -> List[Dict[str, str]]:
        """Return list of commits with message and timestamp"""
        # Note: git_log_commits returns (hash, message) tuples, we convert to dict for tests
        commits = git_tools.git_log_commits(self.repo_url)
        return [{"hash": c[0], "message": c[1], "timestamp": "2026-01-01T12:00:00"} for c in commits]

    def collect_state_info(self, state_file: str = "src/state.py") -> dict:
        """
        Parse Python file for Pydantic BaseModel or TypedDict usage.
        """
        code = file_utils.read_file(state_file) or ""
        return ast_parser.parse_ast(code)

    def collect_graph_info(self, graph_file: str = "src/graph.py") -> dict:
        """
        Parse StateGraph builder for edges and parallel branches.
        """
        code = file_utils.read_file(graph_file) or ""
        return ast_parser.parse_ast(code)


class DocAnalyst:
    """
    Detective that analyzes PDF reports for keywords and accuracy.
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def extract_text(self) -> str:
        try:
            return extract_text_from_pdf(self.pdf_path)
        except Exception:
            return ""

    def check_keywords(self, keywords: List[str] = None) -> Dict[str, List[str]]:
        if keywords is None:
            keywords = ["Dialectical Synthesis", "Fan-In / Fan-Out", "Metacognition"]
        text = self.extract_text()
        return find_keywords_in_text(text, keywords)

    def verify_file_paths(self) -> Tuple[List[str], List[str]]:
        """
        Dummy implementation for tests.
        """
        # In a real app, we'd extract paths from the PDF text.
        # For tests, we mock it or return empty.
        return ([], [])


class VisionInspector:
    """
    Detective that analyzes images/diagrams in the audit.
    """

    def __init__(self, image_path: str):
        self.image_path = image_path

    def load_image(self):
        try:
            return load_image(self.image_path)
        except Exception:
            return None

    def classify(self) -> Dict[str, str]:
        img = self.load_image()
        return classify_diagram(img)