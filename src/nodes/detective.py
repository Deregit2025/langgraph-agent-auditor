# src/nodes/detectives.py

from typing import List, Dict
from src.tools import ast_parser, git_tools, file_utils
from src.tools.docling_utils import extract_text_from_pdf, find_keywords_in_text
from src.tools.vision_utils import load_image, classify_diagram


class RepoInvestigator:
    """
    Detective that analyzes a GitHub repository for forensic evidence.
    """

    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def collect_commit_history(self) -> List[Dict[str, str]]:
        """Return list of commits with message and timestamp"""
        return git_tools.git_log_commits(self.repo_path)

    def analyze_state_management(self, state_file: str) -> str:
        """
        Parse Python file for Pydantic BaseModel or TypedDict usage.
        Returns the AST string or summary.
        """
        code = file_utils.read_file(state_file)
        return ast_parser.parse_ast(code)

    def check_graph_orchestration(self, graph_file: str) -> str:
        """
        Parse StateGraph builder for edges and parallel branches.
        """
        code = file_utils.read_file(graph_file)
        return ast_parser.parse_ast(code)


class DocAnalyst:
    """
    Detective that analyzes PDF reports for keywords and accuracy.
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def extract_text(self) -> str:
        return extract_text_from_pdf(self.pdf_path)

    def find_keywords(self, keywords: List[str]) -> Dict[str, List[str]]:
        text = self.extract_text()
        return find_keywords_in_text(text, keywords)


class VisionInspector:
    """
    Detective that analyzes images/diagrams in the audit.
    """

    def __init__(self, image_path: str):
        self.image_path = image_path

    def load_image(self):
        return load_image(self.image_path)

    def classify(self) -> Dict[str, str]:
        img = self.load_image()
        return classify_diagram(img)