# src/nodes/judges.py

import time
from typing import Optional, Dict, Any
from src.state import JudicialOpinion
from utils.config_loader import load_rubric, get_openai_api_key, get_env, get_llm_provider

class BaseJudge:
    """
    Base class for all judges: evaluates evidence based on the rubric.
    Supports both OpenAI and Google Gemini keys.
    """

    def __init__(self, name: str = "BaseJudge", persona: str = "general"):
        self.name = name
        self.persona = persona.lower()
        self.rubric = load_rubric()
        self.api_key = get_openai_api_key()
        self.model_name = get_env("MODEL_NAME")
        self.provider = get_llm_provider()
        self.llm = None
        
        if (self.api_key and "your_openai_api_key_here" not in self.api_key) or self.provider == "ollama":
            try:
                if self.provider == "ollama":
                    from langchain_ollama import ChatOllama
                    model = self.model_name if self.model_name else "llama3"
                    self.llm = ChatOllama(model=model)
                elif self.api_key.startswith("sk-") or (self.model_name and "gpt" in self.model_name.lower()):
                    from langchain_openai import ChatOpenAI
                    model = self.model_name if self.model_name else "gpt-4o"
                    self.llm = ChatOpenAI(api_key=self.api_key, model=model)
                elif self.api_key.startswith("AIzaSy") or (self.model_name and "gemini" in self.model_name.lower()):
                    from langchain_google_genai import ChatGoogleGenerativeAI
                    model = self.model_name if self.model_name else "models/gemini-2.0-flash"
                    self.llm = ChatGoogleGenerativeAI(api_key=self.api_key, model=model)
            except ImportError:
                pass

    def _get_dimension(self, dimension_id: str) -> Optional[Dict[str, Any]]:
        for dim in self.rubric.get("dimensions", []):
            if dim["id"] == dimension_id:
                return dim
        return None

    def evaluate_dimension(self, dimension_id: str, evidence: str) -> JudicialOpinion:
        """Evaluates a specific rubric dimension using persona logic."""
        dim = self._get_dimension(dimension_id)
        if not dim:
            raise ValueError(f"Dimension {dimension_id} not found in rubric.")

        logic = dim["judicial_logic"].get(self.persona, "Evaluate objectively.")
        instruction = dim["forensic_instruction"]
        
        if self.llm:
            try:
                # Add delay to stay within rate limits for Gemini API
                time.sleep(2)
                return self._evaluate_with_llm(dim, logic, instruction, evidence)
            except Exception as e:
                print(f"[DEBUG] LLM Evaluation failed for {self.name}: {e}")
                # Silently fallback to heuristic if LLM fails (e.g., 404, invalid key)
                return self._evaluate_with_heuristic(dim, logic, instruction, evidence, llm_error=True)
        else:
            return self._evaluate_with_heuristic(dim, logic, instruction, evidence)

    def _evaluate_with_llm(self, dim: Dict, logic: str, instruction: str, evidence: str) -> JudicialOpinion:
        from langchain_core.prompts import ChatPromptTemplate
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"You are the {self.name}. {logic}\nYou must follow this forensic instruction: {instruction}"),
            ("user", f"Evidence gathered:\n{evidence}\n\nProvide your verdict, a score (1-5), and a detailed rationale based on the rubric.")
        ])
        
        response = self.llm.invoke(prompt.format_messages(evidence=evidence))
        content = response.content
        
        return JudicialOpinion(
            judge=self.name,
            criterion=dim["name"],
            verdict="Audit Complete", 
            score=4, 
            rationale=content,
            comments=content[:300] + "..." if len(content) > 300 else content
        )

    def _evaluate_with_heuristic(self, dim: Dict, logic: str, instruction: str, evidence: str, llm_error: bool = False) -> JudicialOpinion:
        """Fallback: Applies rubric logic description to the rationale."""
        score = 3
        verdict = "Audit (Heuristic Fallback)"
        
        note = "LLM analysis skipped (No API key found)."
        if llm_error:
            note = f"LLM analysis skipped (API key detected but model unreachable/invalid)."
        elif self.api_key:
            note = f"LLM analysis skipped (Provider check failed for key starting with '{self.api_key[:5]}')."

        rationale = (
            f"### {self.name}'s Heuristic Assessment\n"
            f"**Judicial Logic Applied**: {logic}\n\n"
            f"**Note**: {note}\n"
        )
        
        return JudicialOpinion(
            judge=self.name,
            criterion=dim["name"],
            verdict=verdict,
            score=score,
            rationale=rationale,
            comments=f"{note} Applied logic: {logic[:100]}..."
        )
        
        return JudicialOpinion(
            judge=self.name,
            criterion=dim["name"],
            verdict=verdict,
            score=score,
            rationale=rationale,
            comments=f"{note} Applied logic: {logic[:100]}..."
        )

class Prosecutor(BaseJudge):
    def __init__(self):
        super().__init__(name="Prosecutor", persona="prosecutor")

class Defense(BaseJudge):
    def __init__(self):
        super().__init__(name="Defense", persona="defense")

class TechLead(BaseJudge):
    def __init__(self):
        super().__init__(name="TechLead", persona="tech_lead")