import os
from typing import Optional


# ------------------------------
# Read a file and return content
# ------------------------------
def read_file(file_path: str) -> Optional[str]:
    """
    Safely read a file and return its content as a string.
    Returns None if file does not exist or cannot be read.
    """
    if not os.path.exists(file_path):
        print(f"[read_file] File not found: {file_path}")
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"[read_file] Failed to read file {file_path}: {e}")
        return None


# ------------------------------
# Write content to a file safely
# ------------------------------
def write_file(file_path: str, content: str) -> bool:
    """
    Safely write content to a file. Creates directories if needed.
    Returns True if successful, False otherwise.
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"[write_file] Failed to write file {file_path}: {e}")
        return False