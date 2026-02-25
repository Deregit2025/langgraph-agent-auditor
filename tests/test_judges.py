from src.nodes.judges import Prosecutor, Defense, TechLead
from src.state import JudicialOpinion

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
    evidence = "Found 5 commits. Pydantic usage detected."
    # Use a real dimension ID from rubric/rubric.json (e.g., 'state_schema')
    dim_id = "forensic_accuracy_code"
    
    # Mock the internal LLM evaluation to avoid actual API calls during tests
    with patch.object(prosecutor_node, "_evaluate_with_llm") as mock_llm:
        mock_llm.return_value = JudicialOpinion(
            judge="Prosecutor",
            criterion="State Schema",
            verdict="Pass",
            score=4,
            rationale="Mocked rationale",
            comments="Mocked comment"
        )
        # We enable LLM logic by ensuring an API key is present or provider is ollama
        prosecutor_node.llm = MagicMock() 
        
        result = prosecutor_node.evaluate_dimension(dim_id, evidence)
        assert result.score == 4
        assert result.judge == "Prosecutor"

def test_defense_evaluate(defense_node):
    """Test Defense evaluation logic"""
    evidence = "Only 2 commits. Sparse documentation."
    dim_id = "forensic_accuracy_code"
    
    # Test heuristic fallback (default behavior when no LLM is configured)
    defense_node.llm = None
    result = defense_node.evaluate_dimension(dim_id, evidence)
    
    assert result.score == 3
    assert "Heuristic" in result.verdict
    assert result.judge == "Defense"

def test_techlead_evaluate(techlead_node):
    """Test TechLead evaluation logic"""
    evidence = "Tool safety verified. Fan-out orchestration confirmed."
    dim_id = "langgraph_architecture"
    
    result = techlead_node.evaluate_dimension(dim_id, evidence)
    assert result.judge == "TechLead"
    assert result.score == 3 # Default heuristic score

def test_judges_agree_disagree(prosecutor_node, defense_node):
    """Test that different judges can return different opinions on the same evidence."""
    evidence = "Test evidence string."
    dim_id = "forensic_accuracy_code"
    
    # Mock different scores
    with patch.object(prosecutor_node, "_evaluate_with_heuristic") as mock_p:
        mock_p.return_value = JudicialOpinion(judge="Prosecutor", criterion="X", verdict="A", score=4, rationale="P", comments="C")
        with patch.object(defense_node, "_evaluate_with_heuristic") as mock_d:
            mock_d.return_value = JudicialOpinion(judge="Defense", criterion="X", verdict="B", score=2, rationale="D", comments="C")
            
            p_opinion = prosecutor_node.evaluate_dimension(dim_id, evidence)
            d_opinion = defense_node.evaluate_dimension(dim_id, evidence)
            
            assert p_opinion.score != d_opinion.score