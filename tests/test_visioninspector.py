# tests/test_visioninspector.py
import pytest
from unittest.mock import patch, MagicMock
from src.nodes.detectives import VisionInspector

SAMPLE_IMAGE_PATH = "audit/diagram.png"

@pytest.fixture
def vision_inspector():
    """Create a VisionInspector instance for testing."""
    return VisionInspector(image_path=SAMPLE_IMAGE_PATH)

def test_load_image(vision_inspector):
    """Test that load_image returns an image object."""
    with patch("src.nodes.detectives.load_image", return_value=MagicMock()):
        img = vision_inspector.load_image()
        assert img is not None

def test_classify(vision_inspector):
    """Test that classify returns a dictionary."""
    with patch("src.nodes.detectives.VisionInspector.load_image", return_value=MagicMock()):
        with patch("src.nodes.detectives.classify_diagram", return_value={"type": "test", "description": "test"}):
            result = vision_inspector.classify()
            assert isinstance(result, dict)
            assert "type" in result
            assert result["type"] == "test"
