# src/nodes/detectives.py

from typing import List, Dict, Tuple
from src.tools import ast_parser, file_utils
from src.tools.git_tools import git_log_commits, get_current_sha, GitToolError
from src.tools.docling_utils import ForensicPDFReader, find_keywords_in_text
from src.tools.vision_utils import load_image, classify_diagram


class RepoInvestigator:
    """
    Detective that analyses a Git repository for forensic evidence.

    Uses sandboxed shallow cloning (remote) or direct path (local).
    All git failures surface as ``GitToolError`` with descriptive messages
    rather than bare ``CalledProcessError`` tracebacks.
    """

    def __init__(self, repo_url: str):
        self.repo_url = repo_url
        self.rubric = None
        try:
            from utils.config_loader import load_rubric
            self.rubric = load_rubric()
        except ImportError:
            pass

    def collect_git_commits(self) -> List[Dict[str, str]]:
        """
        Return list of commits as dicts with 'hash', 'message', 'timestamp'.

        Raises
        ------
        GitToolError
            If the repo cannot be cloned or git log fails, with a clear
            explanation of which step failed and why.
        """
        try:
            commits = git_log_commits(self.repo_url)
        except GitToolError as exc:
            print(f"[RepoInvestigator] Git failure: {exc}")
            raise

        return [
            {"hash": c[0], "message": c[1], "timestamp": "2026-01-01T12:00:00"}
            for c in commits
        ]

    def collect_current_sha(self) -> str:
        """
        Return the HEAD SHA of the local repo (for self-audit traceability).

        Returns an empty string if the SHA cannot be resolved, so callers
        do not need to wrap this in a try/except for non-critical traces.
        """
        try:
            return get_current_sha(self.repo_url if self.repo_url != "." else ".")
        except GitToolError as exc:
            print(f"[RepoInvestigator] Could not resolve HEAD SHA: {exc}")
            return ""

    def collect_state_info(self, state_file: str = "src/state.py") -> dict:
        """
        Parse *state_file* for Pydantic BaseModel / TypedDict usage via AST.
        """
        code = file_utils.read_file(state_file) or ""
        return ast_parser.parse_ast(code)

    def collect_graph_info(self, graph_file: str = "src/graph.py") -> dict:
        """
        Parse *graph_file* for StateGraph edges and parallel branches via AST.
        """
        code = file_utils.read_file(graph_file) or ""
        return ast_parser.parse_ast(code)

    def collect_tool_safety_info(self, tool_file: str = "src/tools/git_tools.py") -> dict:
        """
        Forensically check for 'GIT_TERMINAL_PROMPT=0' and sandboxing in Git tools.
        """
        code = file_utils.read_file(tool_file) or ""
        return {
            "has_sandboxing": "clone_repo_sandbox" in code,
            "has_prompt_guard": "GIT_TERMINAL_PROMPT" in code and "0" in code,
            "has_tempfile": "tempfile.mkdtemp" in code,
            "snippet": code[:500] if code else ""
        }

    def collect_judicial_nuance_info(self, judge_file: str = "src/nodes/judges.py") -> dict:
        """
        Verify that Prosecutor, Defense, and TechLead personas have distinct prompts 
        and check if output instructions favor structured data.
        """
        code = file_utils.read_file(judge_file) or ""
        
        # Check for persona-specific logic in the rubric if available
        persona_logic = {}
        if self.rubric:
            for dim in self.rubric.get("dimensions", []):
                if dim["id"] == "judicial_nuance":
                    persona_logic = dim.get("judicial_logic", {})
        
        return {
            "prompt_construction": "ChatPromptTemplate.from_messages" in code,
            "has_persona_logic": len(persona_logic) > 0,
            "logic_snippets": persona_logic,
            "json_intent": "verdict" in code and "score" in code and "rationale" in code
        }


class DocAnalyst:
    """
    Detective that forensically analyses a PDF report using a chunked,
    queryable interface.

    Instead of working on one giant text blob, the analyst loads the PDF into
    per-page ``PDFChunk`` objects and asks targeted keyword questions using
    ``ForensicPDFReader.query()``.  This keeps evidence descriptions concise
    and avoids overwhelming the Judge layer with irrelevant text.
    """

    # Default keywords the grader is likely looking for in an audit report
    DEFAULT_KEYWORDS = [
        "StateGraph",
        "Pydantic",
        "Fan-Out",
        "Fan-In",
        "Dialectical Synthesis",
        "Metacognition",
        "Reducer",
        "Evidence",
    ]

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self._reader: ForensicPDFReader | None = None

    def _get_reader(self) -> ForensicPDFReader:
        """Lazily load the PDF and cache the reader."""
        if self._reader is None:
            self._reader = ForensicPDFReader(self.pdf_path).load()
        return self._reader

    def extract_text(self) -> str:
        """
        Return the full PDF text (legacy interface).

        Prefer :meth:`query_for` for forensic analysis.
        """
        try:
            return self._get_reader().full_text()
        except Exception as exc:
            print(f"[DocAnalyst] Could not extract text from '{self.pdf_path}': {exc}")
            return ""

    def query_for(self, keyword: str) -> List[str]:
        """
        Targeted query: return matching sentences for *keyword* across all pages.

        Parameters
        ----------
        keyword : str
            The forensic term to search for (e.g. 'StateGraph', 'Reducer').

        Returns
        -------
        List[str]
            Matching sentences from any page, or an empty list if not found.
        """
        try:
            reader = self._get_reader()
            sentences: List[str] = []
            for chunk in reader.query(keyword):
                sentences.extend(chunk.matching_sentences(keyword))
            return sentences
        except Exception as exc:
            print(f"[DocAnalyst] query_for('{keyword}') failed: {exc}")
            return []

    def check_keywords(self, keywords: List[str] = None) -> Dict[str, dict]:
        """
        Return a structured forensic summary for each keyword using the
        ``ForensicPDFReader.keyword_summary()`` method.

        Each entry contains: hit_count, page_numbers, contexts.
        """
        if keywords is None:
            keywords = self.DEFAULT_KEYWORDS
        try:
            return self._get_reader().keyword_summary(keywords)
        except Exception as exc:
            print(f"[DocAnalyst] keyword summary failed: {exc}")
            # Fallback: return empty structure so upstream code doesn't crash
            return {kw: {"hit_count": 0, "page_numbers": [], "contexts": []} for kw in keywords}

    def verify_file_paths(self) -> Tuple[List[str], List[str]]:
        """
        Scan the PDF/MD text for file path patterns and verify they exist on disk.
        """
        import re
        import os

        # Match common path patterns like src/graph.py or audit/report.md
        path_pattern = re.compile(r'\b[\w./\\-]+\.(?:py|md|json|yaml|yml|txt|pdf)\b')

        # Use the reader to get all text across chunks
        try:
            text = self.extract_text()
        except Exception:
            return [], []

        candidate_paths = list(set(path_pattern.findall(text)))

        found: List[str] = []
        missing: List[str] = []
        for p in candidate_paths:
            # Clean trailing punctuation
            clean_p = p.rstrip('.,;)]}')
            if os.path.exists(clean_p) and os.path.isfile(clean_p):
                found.append(clean_p)
            elif "/" in clean_p or "\\" in clean_p: # only count strings that look like paths
                missing.append(clean_p)

        return list(set(found)), list(set(missing))


class VisionInspector:
    """
    Detective that analyses image/diagram artefacts in the audit submission.
    """

    def __init__(self, image_path: str):
        self.image_path = image_path

    def load_image(self):
        try:
            return load_image(self.image_path)
        except Exception as exc:
            print(f"[VisionInspector] Could not load image '{self.image_path}': {exc}")
            return None

    def classify(self) -> Dict[str, str]:
        img = self.load_image()
        return classify_diagram(img)