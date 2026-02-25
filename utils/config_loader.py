import os
from pathlib import Path
from dotenv import load_dotenv
import json

# Load .env file at project root
BASE_DIR = Path(__file__).resolve().parent.parent
dotenv_path = BASE_DIR / ".env"
load_dotenv(dotenv_path)

def get_env(var_name: str, default=None):
    """Get environment variable or return default."""
    return os.getenv(var_name, default)

def load_rubric(filename="rubric/rubric.json"):
    """Load rubric JSON as Python dict."""
    rubric_path = BASE_DIR / filename
    if not rubric_path.exists():
        raise FileNotFoundError(f"Rubric file not found: {rubric_path}")
    with open(rubric_path, "r", encoding="utf-8") as f:
        return json.load(f)

# Convenience functions for commonly used env variables
def get_google_api_key():
    return get_env("GOOGLE_API_KEY")

def get_openai_api_key():
    return get_env("OPENAI_API_KEY")

def get_test_repo_url():
    return get_env("TEST_REPO_URL_PEER")

def get_self_repo_url():
    return get_env("TEST_REPO_URL_SELF")

def get_llm_provider():
    return get_env("LLM_PROVIDER")

def get_llm_base_url():
    return get_env("LLM_BASE_URL")