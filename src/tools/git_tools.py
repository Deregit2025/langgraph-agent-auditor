import subprocess
import tempfile
import os
from typing import List, Tuple


# ------------------------------
# Clone a repo to a temporary sandbox and return path
# ------------------------------
def clone_repo_sandbox(repo_url: str) -> str:
    """
    Clone the repo into a temporary directory for safe inspection.
    Returns the path to the cloned repo.
    """
    temp_dir = tempfile.TemporaryDirectory()
    subprocess.run(
        ["git", "clone", repo_url, temp_dir.name],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return temp_dir.name


# ------------------------------
# List commits in a repo (most recent last)
# ------------------------------
def git_log_commits(repo_url: str, max_commits: int = 100) -> List[Tuple[str, str]]:
    """
    Clone the repo into a sandbox and return a list of commits.
    Each commit is a tuple: (commit_hash, commit_message)
    """
    repo_path = clone_repo_sandbox(repo_url)
    # Run git log
    result = subprocess.run(
        ["git", "-C", repo_path, "log", "--oneline", f"-n{max_commits}", "--reverse"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    commits = []
    for line in result.stdout.strip().split("\n"):
        if line:
            parts = line.split(" ", 1)
            if len(parts) == 2:
                commit_hash, commit_message = parts
                commits.append((commit_hash, commit_message))
            else:
                commits.append((parts[0], ""))

    return commits