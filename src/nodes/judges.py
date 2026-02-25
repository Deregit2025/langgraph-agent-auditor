# src/nodes/judges.py

import time
from typing import Optional, Dict, Any
from src.state import JudicialOpinion
from utils.config_loader import load_rubric, get_openai_api_key, get_google_api_key, get_env, get_llm_provider

class BaseJudge:
    """
    Base class for all judges: evaluates evidence based on the rubric.
    Supports OpenAI, Google Gemini, and Ollama.
    """

    def __init__(self, name: str = "BaseJudge", persona: str = "general"):
        self.name = name
        self.persona = persona.lower()
        self.rubric = load_rubric()
        self.provider = get_llm_provider()
        self.model_name = get_env("MODEL_NAME")
        self.llm = None
        
        # Select key based on provider
        if self.provider == "google":
            self.api_key = get_google_api_key()
        else:
            self.api_key = get_openai_api_key()
            
        if (self.api_key and "your_key_here" not in str(self.api_key)) or self.provider == "ollama":
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
        from langchain_core.messages import SystemMessage, HumanMessage
        
        # We avoid ChatPromptTemplate here to prevent KeyError from curly braces in evidence snippet
        messages = [
            SystemMessage(content=f"You are the {self.name}. {logic}\nYou must follow this forensic instruction: {instruction}"),
            HumanMessage(content=f"Evidence gathered for criterion '{dim['name']}':\n\n{evidence}\n\nProvide your verdict, a score (1-5), and a detailed rationale based on the rubric.")
        ]
        
        response = self.llm.invoke(messages)
        content = response.content
        
        return JudicialOpinion(
            judge=self.name,
            criterion=dim["name"],
            verdict="Audit Complete", 
            score=4, # Fallback score if parser fails; LLM logic should ideally return JSON
            rationale=content,
            comments=content[:300] + "..." if len(content) > 300 else content
        )

    def _evaluate_with_heuristic(self, dim: Dict, logic: str, instruction: str, evidence: str, llm_error: bool = False) -> JudicialOpinion:
        """Fallback: Applies rubric logic and scans evidence for forensic alignment."""
        score = 3
        verdict = "Audit (Heuristic Fallback)"
        
        # Simple evidence scan for "Forensic Proof"
        evidence_hits = []
        if "found=True" in evidence.replace(" ", ""):
            score = 4
            evidence_hits.append("Positive indicators found in forensic logs.")
        if "found=False" in evidence.replace(" ", ""):
            score = 2
            evidence_hits.append("Critical gaps or missing artifacts detected.")
            
        # Persona-specific keyword scan
        if self.persona == "prosecutor" and ("error" in evidence.lower() or "missing" in evidence.lower()):
            score = max(1, score - 1)
            evidence_hits.append("Prosecutor identified potential negligence.")
        
        note = "LLM analysis skipped (No API key found)."
        if llm_error:
            note = f"LLM analysis skipped (Technical error encountered while evaluating evidence)."
        
        evidence_summary = "\n- ".join(evidence_hits) if evidence_hits else "No conclusive patterns found in raw evidence strings."

        rationale = (
            f"### {self.name}'s Heuristic Assessment\n"
            f"**Judicial Logic Applied**: {logic}\n\n"
            f"**Forensic Verification**: \n- {evidence_summary}\n\n"
            f"**Note**: {note}\n"
        )
        
        return JudicialOpinion(
            judge=self.name,
            criterion=dim["name"],
            verdict=verdict,
            score=score,
            rationale=rationale,
            comments=f"{note} Forensic scan result: {score}/5"
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