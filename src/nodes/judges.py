# src/nodes/judges.py

from typing import List, Dict
from src.tools.ast_parser import parse_ast
from src.tools.git_tools import git_log_commits
from src.tools.file_utils import read_file
from pydantic import BaseModel


class JudicialOpinion(BaseModel):
    judge_name: str
    verdict: str
    score: int
    comments: str


class BaseJudge:
    """
    Base class for all judges: evaluates evidence collected by detectives.
    """

    def __init__(self, name: str):
        self.name = name

    def evaluate_commit_history(self, repo_path: str) -> JudicialOpinion:
        commits = git_log_commits(repo_path)
        score = min(len(commits), 5)  # simple scoring logic
        verdict = "Pass" if score > 3 else "Fail"
        comments = f"{len(commits)} commits found."
        return JudicialOpinion(
            judge_name=self.name, verdict=verdict, score=score, comments=comments
        )

    def evaluate_state_management(self, state_file: str) -> JudicialOpinion:
        code_ast = parse_ast(read_file(state_file))
        verdict = "Structured" if "BaseModel" in code_ast else "Loose"
        score = 5 if verdict == "Structured" else 2
        comments = f"State parsed from {state_file}."
        return JudicialOpinion(
            judge_name=self.name, verdict=verdict, score=score, comments=comments
        )

    def evaluate_graph(self, graph_file: str) -> JudicialOpinion:
        code_ast = parse_ast(read_file(graph_file))
        # Fan-in / Fan-out detection (simplified)
        fan_out = "builder.add_edge" in code_ast
        verdict = "Parallel" if fan_out else "Linear"
        score = 5 if fan_out else 1
        comments = "Detected parallel branches" if fan_out else "Linear flow detected"
        return JudicialOpinion(
            judge_name=self.name, verdict=verdict, score=score, comments=comments
        )


class Prosecutor(BaseJudge):
    pass  # specialized logic can be added later


class Defense(BaseJudge):
    pass  # specialized logic can be added later


class TechLead(BaseJudge):
    pass  # specialized logic can be added later