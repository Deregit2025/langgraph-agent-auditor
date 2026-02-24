# src/tools/vision_utils.py

from PIL import Image
from pathlib import Path
from typing import Dict

def load_image(image_path: str) -> Image.Image:
    """
    Loads an image from disk.
    """
    img_file = Path(image_path)
    if not img_file.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    return Image.open(img_file)

def classify_diagram(image: Image.Image) -> Dict[str, str]:
    """
    Dummy function to classify diagrams.
    Returns a dict with type and description.
    """
    # For now, we can just return a placeholder
    return {
        "type": "LangGraph diagram",
        "description": "Diagram represents parallel branches: Evidence Aggregation -> Detectives -> Chief Justice"
    }