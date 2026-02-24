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
    temp_dir = tempfile.mkdtemp()
    subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, temp_dir],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return temp_dir


# ------------------------------
# List commits in a repo (most recent last)
# ------------------------------
def git_log_commits(repo_url: str, max_commits: int = 100) -> List[Tuple[str, str]]:
    """
    If repo_url is a URL, clone into a sandbox.
    If repo_url is a local path (exists), use it directly.
    Returns a list of commits. Each commit is a tuple: (commit_hash, commit_message)
    """
    is_local = os.path.isdir(repo_url)
    repo_path = repo_url if is_local else clone_repo_sandbox(repo_url)
    
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