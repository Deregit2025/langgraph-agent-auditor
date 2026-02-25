"""
git_tools.py — Sandboxed Git operations for the RepoInvestigator detective.

All git interactions are performed via ``subprocess.run`` (never ``os.system``)
with tightly scoped error handling.  Every failure raises a descriptive
``GitToolError`` so the caller knows *exactly* what went wrong and at which step.

Security notes
--------------
* Remote repositories are cloned with ``--depth 1`` to prevent history-based
  attacks and minimise clone time.
* The clone target is always a ``tempfile.mkdtemp()`` directory, guaranteeing
  no cross-audit contamination.
* ``GIT_TERMINAL_PROMPT=0`` is injected into the subprocess environment so git
  never blocks waiting for interactive credentials — it will fail fast and
  cleanly instead.
"""

import os
import subprocess
import tempfile
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class GitToolError(RuntimeError):
    """
    Raised when any git operation fails.

    Attributes
    ----------
    step    : Short label for which operation failed (e.g. 'clone', 'log').
    repo    : The repo URL or path that was being operated on.
    detail  : The raw stderr output from git, if available.
    """

    def __init__(self, step: str, repo: str, detail: str = ""):
        self.step = step
        self.repo = repo
        self.detail = detail
        message = (
            f"[GitTool] '{step}' failed for repo '{repo}'."
            + (f"\n  git stderr: {detail.strip()}" if detail.strip() else "")
        )
        super().__init__(message)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_run(args: List[str], step: str, repo: str) -> subprocess.CompletedProcess:
    """
    Run a git command, capturing stdout/stderr.

    Raises ``GitToolError`` with a clear message when the command fails,
    instead of letting a ``CalledProcessError`` with an opaque traceback
    bubble up to the detective layer.
    """
    # Prevent interactive credential prompts from hanging the process
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        result = subprocess.run(
            args,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        return result
    except subprocess.CalledProcessError as exc:
        raise GitToolError(
            step=step,
            repo=repo,
            detail=exc.stderr or "",
        ) from exc
    except FileNotFoundError:
        raise GitToolError(
            step=step,
            repo=repo,
            detail="'git' executable not found on PATH. Is git installed?",
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def clone_repo_sandbox(repo_url: str) -> str:
    """
    Shallow-clone *repo_url* into a fresh temporary directory.

    Parameters
    ----------
    repo_url : str
        HTTPS or SSH URL of the remote git repository.

    Returns
    -------
    str
        Absolute path to the cloned repository on disk.

    Raises
    ------
    GitToolError
        If the clone fails (bad URL, network error, auth failure, etc.).
    """
    temp_dir = tempfile.mkdtemp(prefix="langgraph_audit_")
    _safe_run(
        ["git", "clone", "--depth", "1", repo_url, temp_dir],
        step="clone",
        repo=repo_url,
    )
    return temp_dir


def git_log_commits(repo_url: str, max_commits: int = 100) -> List[Tuple[str, str]]:
    """
    Return a list of recent commits from *repo_url*.

    If *repo_url* is a local directory path it is used directly (no clone).
    If it is a remote URL it is first shallow-cloned via :func:`clone_repo_sandbox`.

    Parameters
    ----------
    repo_url    : str
        Local path or remote URL of the repository.
    max_commits : int
        Maximum number of commits to return (default 100).

    Returns
    -------
    List[Tuple[str, str]]
        Each element is ``(commit_hash, commit_message)``.

    Raises
    ------
    GitToolError
        If the git log command fails (not a git repo, corrupt history, etc.).
    """
    is_local = os.path.isdir(repo_url)

    if is_local:
        repo_path = repo_url
    else:
        try:
            repo_path = clone_repo_sandbox(repo_url)
        except GitToolError:
            # Re-raise with additional context so the detective log is clear
            raise GitToolError(
                step="clone-before-log",
                repo=repo_url,
                detail=(
                    "Could not clone the repository. "
                    "Check that the URL is correct and the network is reachable."
                ),
            )

    result = _safe_run(
        ["git", "-C", repo_path, "log", "--oneline", f"-n{max_commits}", "--reverse"],
        step="log",
        repo=repo_url,
    )

    commits: List[Tuple[str, str]] = []
    for line in result.stdout.strip().splitlines():
        if line:
            parts = line.split(" ", 1)
            if len(parts) == 2:
                commits.append((parts[0], parts[1]))
            else:
                commits.append((parts[0], ""))

    return commits


def get_current_sha(repo_path: str = ".") -> str:
    """
    Return the full SHA of the current HEAD commit for a local repository.

    Parameters
    ----------
    repo_path : str
        Path to the local repository root (default: current directory).

    Returns
    -------
    str
        40-character hex SHA of HEAD.

    Raises
    ------
    GitToolError
        If the repo path is invalid or HEAD cannot be resolved.
    """
    result = _safe_run(
        ["git", "-C", repo_path, "rev-parse", "HEAD"],
        step="rev-parse",
        repo=repo_path,
    )
    return result.stdout.strip()