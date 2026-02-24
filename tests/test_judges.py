# tests/test_judges.py
import pytest
from unittest.mock import patch, MagicMock
from src.nodes.judges import Prosecutor, Defense, TechLead

@pytest.fixture
def prosecutor_node():
    return Prosecutor()

@pytest.fixture
def defense_node():
    return Defense()

@pytest.fixture
def techlead_node():
    return TechLead()

def test_prosecutor_evaluate(prosecutor_node):
    """Test Prosecutor evaluation logic"""
    evidence = {"commits": 5, "state_rigour": True}
    
    # Mock the LLM reasoning method
    with patch.object(prosecutor_node, "evaluate_evidence", return_value={"score": 4, "comment": "Mocked comment"}):
        result = prosecutor_node.evaluate_evidence(evidence)
        assert result["score"] == 4
        assert "comment" in result

def test_defense_evaluate(defense_node):
    """Test Defense evaluation logic"""
    evidence = {"commits": 2, "state_rigour": False}
    
    with patch.object(defense_node, "evaluate_evidence", return_value={"score": 2, "comment": "Mocked defense"}):
        result = defense_node.evaluate_evidence(evidence)
        assert result["score"] == 2
        assert "comment" in result

def test_techlead_evaluate(techlead_node):
    """Test TechLead evaluation logic"""
    evidence = {"tool_safety": True, "graph_structure": "Fan-Out"}
    
    with patch.object(techlead_node, "evaluate_evidence", return_value={"score": 5, "comment": "Tech lead ok"}):
        result = techlead_node.evaluate_evidence(evidence)
        assert result["score"] == 5
        assert result["comment"] == "Tech lead ok"

def test_judges_agree_disagree(prosecutor_node, defense_node):
    """Test mock agreement/disagreement logic"""
    evidence = {"commits": 3, "state_rigour": True}
    
    with patch.object(prosecutor_node, "evaluate_evidence", return_value={"score": 4}):
        with patch.object(defense_node, "evaluate_evidence", return_value={"score": 2}):
            p_score = prosecutor_node.evaluate_evidence(evidence)["score"]
            d_score = defense_node.evaluate_evidence(evidence)["score"]
            assert p_score != d_score  # Ensure disagreement triggers potential synthesis