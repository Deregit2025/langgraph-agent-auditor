# src/nodes/judges.py

import time
from typing import Optional, Dict, Any
from src.state import JudicialOpinion
from utils.config_loader import load_rubric, get_google_api_key, get_openrouter_api_key, get_env, get_llm_provider, get_llm_base_url, get_llm_model_name

class BaseJudge:
    """
    Base class for all judges: evaluates evidence based on the rubric.
    Supports Google Gemini, OpenRouter, and Ollama.
    """

    def __init__(self, name: str = "BaseJudge", persona: str = "general"):
        self.name = name
        self.persona = persona.lower()
        self.rubric = load_rubric()
        self.provider = get_llm_provider().lower()
        self.model_name = get_llm_model_name()
        self.llm = None
        
        try:
            if self.provider == "ollama":
                from langchain_ollama import ChatOllama
                model = self.model_name if self.model_name else "llama3"
                base_url = get_llm_base_url()
                self.llm = ChatOllama(model=model, base_url=base_url)
                print(f"[*] {self.name}: Initialized Ollama ({model})")

            elif self.provider == "google":
                from langchain_google_genai import ChatGoogleGenerativeAI
                api_key = get_google_api_key()
                if api_key:
                    model = self.model_name if self.model_name else "gemini-2.0-flash"
                    self.llm = ChatGoogleGenerativeAI(api_key=api_key, model=model)
                    print(f"[*] {self.name}: Initialized Google Gemini ({model})")

            elif self.provider == "openrouter":
                from langchain_openai import ChatOpenAI
                api_key = get_openrouter_api_key()
                if api_key:
                    model = self.model_name if self.model_name else "google/gemini-2.0-flash-001"
                    self.llm = ChatOpenAI(
                        api_key=api_key, 
                        model=model, 
                        base_url="https://openrouter.ai/api/v1"
                    )
                    print(f"[*] {self.name}: Initialized OpenRouter ({model})")
        except ImportError as e:
            print(f"[!] {self.name}: Failed to import required library for {self.provider}: {e}")
        except Exception as e:
            print(f"[!] {self.name}: Error initializing {self.provider}: {e}")

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

        # Support both rubric v2 (judicial_logic dict) and v3 (success_pattern / failure_pattern)
        judicial_logic = dim.get("judicial_logic", {})
        logic = judicial_logic.get(self.persona, None)

        if not logic:
            # Build persona-appropriate guidance from v3 rubric fields
            success = dim.get("success_pattern", "Evaluate the evidence for quality and correctness.")
            failure = dim.get("failure_pattern", "Flag any missing or incorrect artifacts.")
            if self.persona == "prosecutor":
                logic = f"Look critically for failures and gaps. Failure pattern to watch for: {failure}"
            elif self.persona == "defense":
                logic = f"Highlight effort, creativity, and what was done well. Success pattern: {success}"
            else:  # tech_lead
                logic = f"Evaluate architectural soundness and practicality. Success: {success}. Failure: {failure}"

        instruction = dim.get("forensic_instruction", "Apply your forensic judgment to the evidence provided.")
        
        if self.llm:
            try:
                # Add delay to stay within rate limits for Gemini API only
                if self.provider == "google":
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
        import json
        import re
        
        # We avoid ChatPromptTemplate here to prevent KeyError from curly braces in evidence snippet
        messages = [
            SystemMessage(content=(
                f"You are the {self.name}. {logic}\n"
                f"You must follow this forensic instruction: {instruction}\n\n"
                "Respond ONLY with a JSON object in this exact format (no markdown, no extra text):\n"
                '{"verdict": "Pass|Fail|Partial", "score": <integer 1-5>, "rationale": "<detailed reasoning>"}'
            )),
            HumanMessage(content=(
                f"Evidence gathered for criterion '{dim['name']}':\n\n{evidence}\n\n"
                "Provide your verdict, a score (1-5), and a detailed rationale based on the rubric."
            ))
        ]
        
        response = self.llm.invoke(messages)
        content = response.content
        
        # Parse structured JSON from LLM response
        parsed_verdict = "Audit Complete"
        parsed_score = 4
        parsed_rationale = content
        
        try:
            # Try to extract JSON block even if the model adds preamble
            json_match = re.search(r'\{[^{}]+\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                parsed_verdict = str(data.get("verdict", "Audit Complete"))
                raw_score = int(data.get("score", 4))
                parsed_score = max(1, min(5, raw_score))  # clamp to [1, 5]
                parsed_rationale = str(data.get("rationale", content))
        except (json.JSONDecodeError, ValueError, TypeError):
            # If parsing fails, use full content as rationale and keep defaults
            print(f"[DEBUG] {self.name}: Could not parse JSON from LLM response. Using raw content.")
        
        return JudicialOpinion(
            judge=self.name,
            criterion=dim["name"],
            verdict=parsed_verdict,
            score=parsed_score,
            rationale=parsed_rationale,
            comments=parsed_rationale[:300] + "..." if len(parsed_rationale) > 300 else parsed_rationale
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