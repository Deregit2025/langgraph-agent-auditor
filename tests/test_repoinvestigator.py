# tests/test_repoinvestigator.py
import pytest
from unittest.mock import patch, MagicMock
from src.nodes.detectives import RepoInvestigator
from src.tools.git_tools import git_log_commits
from src.tools.file_utils import read_file

# Sample repo URL for testing
SAMPLE_REPO = "https://github.com/test/test-repo.git"

@pytest.fixture
def repo_investigator():
    """Create a RepoInvestigator instance for testing."""
    return RepoInvestigator(repo_url=SAMPLE_REPO)

def test_collect_git_commits(repo_investigator):
    """Test that collect_git_commits returns a list of commits."""
    # Mocking git_log_commits to return a list of (hash, message) tuples
    sample_commits = [
        ("a1b2c3", "Initial commit"),
        ("d4e5f6", "Add README"),
    ]

    with patch("src.nodes.detectives.git_tools.git_log_commits", return_value=sample_commits):
        commits = repo_investigator.collect_git_commits()
        assert isinstance(commits, list)
        assert len(commits) == 2
        assert commits[0]["hash"] == "a1b2c3"

def test_collect_state_info(repo_investigator):
    """Test that collect_state_info returns structured state info."""
    # Patch read_file to simulate reading src/state.py
    sample_state_content = """
from pydantic import BaseModel

class Evidence(BaseModel):
    name: str

class JudicialOpinion(BaseModel):
    verdict: str
"""
    with patch("src.nodes.detectives.file_utils.read_file", return_value=sample_state_content):
        state_info = repo_investigator.collect_state_info()
        assert "Evidence" in state_info["classes"]
        assert "JudicialOpinion" in state_info["classes"]

def test_collect_graph_info(repo_investigator):
    """Test that collect_graph_info returns graph structure info."""
    # Patch read_file to simulate reading src/graph.py
    sample_graph_content = """
from src.state import Evidence
class StateGraph:
    def add_edge(self, from_node, to_node):
        pass
"""
    with patch("src.nodes.detectives.file_utils.read_file", return_value=sample_graph_content):
        graph_info = repo_investigator.collect_graph_info()
        assert "StateGraph" in graph_info["classes"]