"""
state.py — Canonical State Schema for the LangGraph Auditor.

This module defines the three core data models used to represent the shared
mutable state of the audit graph:

  - Evidence       : A forensic artefact collected by a Detective node.
  - JudicialOpinion: A structured verdict produced by a Judge node.
  - AgentState     : The top-level state object passed between every node.

Design principles
-----------------
* Pydantic BaseModel is used (instead of TypedDict or plain dicts) for strict
  runtime validation, serialisation, and IDE-level type safety.
* List fields carry ``Annotated[List[...], operator.add]`` reducer hints so
  that parallel Detective / Judge fan-out nodes can append to their respective
  lists concurrently without overwriting each other's data (CRDT append-only
  semantics).
* Numerical fields are constrained at the model level (``ge`` / ``le``) so
  corrupt data is rejected at the node boundary rather than silently
  propagating to downstream synthesis.
"""

import operator
from datetime import datetime
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Evidence — produced by Detective nodes
# ---------------------------------------------------------------------------

class Evidence(BaseModel):
    """
    A single piece of forensic evidence collected by a Detective agent.

    Detectives run in parallel fan-out; the ``AgentState.evidence_collection``
    field uses an ``operator.add`` reducer so each Detective's output is *merged*
    (list concatenation) rather than overwritten when the fan-in occurs.

    Rich evidence fields
    --------------------
    goal        : What the detective was trying to verify (the forensic question).
    found       : Whether the artifact or pattern was actually located.
    location    : File path, page number, or section where the evidence lives.
    rationale   : The detective's reasoning chain justifying this evidence entry.
    content     : A short verbatim extract (code snippet, sentence, label).
    confidence  : Numeric certainty [0.0 – 1.0] in this piece of evidence.
    """

    source: str = Field(
        description=(
            "Which Detective collected this evidence. "
            "Expected values: 'RepoInvestigator', 'DocAnalyst', 'VisionInspector'."
        )
    )
    type: str = Field(
        description=(
            "Category of evidence. "
            "e.g. 'git_commit', 'file_scan', 'pdf_text', 'diagram_classification', "
            "'missing_artifact'."
        )
    )
    description: str = Field(
        description="A concise human-readable summary of what was found (or not found)."
    )
    # --- Rich forensic fields ---
    goal: Optional[str] = Field(
        default=None,
        description=(
            "The forensic question this evidence answers. "
            "e.g. 'Does src/state.py use Pydantic BaseModel?'"
        ),
    )
    found: Optional[bool] = Field(
        default=None,
        description=(
            "True  = the artifact / pattern was located and verified. "
            "False = the artifact was expected but missing (absent evidence). "
            "None  = not applicable (e.g. informational log entries)."
        ),
    )
    location: Optional[str] = Field(
        default=None,
        description=(
            "Where in the codebase or document this evidence was found. "
            "e.g. 'src/state.py:L8', 'PDF page 3', 'git commit a1b2c3d'."
        ),
    )
    rationale: Optional[str] = Field(
        default=None,
        description=(
            "The detective's reasoning: why this evidence supports or refutes "
            "the goal. Surfaced in Judge prompts as supporting context."
        ),
    )
    content: Optional[str] = Field(
        default=None,
        description=(
            "Optional verbatim extracted content: a code snippet, a PDF sentence, "
            "or a diagram label. Kept short to stay within Judge context windows."
        ),
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description=(
            "Detective's confidence in this evidence, in the range [0.0, 1.0]. "
            "1.0 = fully verified (e.g. AST parse succeeded). "
            "0.0 = artifact missing or parse completely failed."
        ),
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp of when the evidence was collected.",
    )


# ---------------------------------------------------------------------------
# JudicialOpinion — produced by Judge nodes
# ---------------------------------------------------------------------------

class JudicialOpinion(BaseModel):
    """
    A structured verdict produced by a Judge agent for a single rubric dimension.

    Judges run in parallel fan-out; the ``AgentState.judicial_opinions`` field
    uses an ``operator.add`` reducer so all three Judges' outputs are merged
    (list concatenation) rather than overwritten during the fan-in phase.
    """

    judge: str = Field(
        description=(
            "Name of the Judge persona who produced this opinion. "
            "Expected values: 'Prosecutor', 'Defense', 'TechLead'."
        )
    )
    criterion: str = Field(
        description="The rubric dimension name this opinion evaluates (e.g. 'State Schema Quality')."
    )
    verdict: str = Field(
        description=(
            "Short verdict label, e.g. 'Pass', 'Fail', 'Partial', "
            "'Audit Complete', 'Audit (Heuristic Fallback)'."
        )
    )
    score: int = Field(
        ge=1,
        le=5,
        description=(
            "Numerical score for this criterion in the range [1, 5]. "
            "1 = critically non-compliant, 5 = exemplary."
        ),
    )
    rationale: str = Field(
        description=(
            "Detailed explanation of the score. For LLM-backed judges this is the "
            "raw model output; for heuristic fallback it is the rule-based justification."
        )
    )
    comments: str = Field(
        description=(
            "Executive-level highlights (≤ 300 chars) surfaced in the final report's "
            "Executive Summary section."
        )
    )
    evidence_ids: Optional[List[int]] = Field(
        default=None,
        description=(
            "Zero-based indexes into ``AgentState.evidence_collection`` that this "
            "opinion draws upon, enabling cross-referencing in the final report."
        ),
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp of when the opinion was produced.",
    )


# ---------------------------------------------------------------------------
# AgentState — top-level graph state
# ---------------------------------------------------------------------------

class AgentState(BaseModel):
    """
    The shared mutable state propagated through every node in the StateGraph.

    Reducer semantics
    -----------------
    Both list fields are annotated with ``operator.add`` as their reducer.
    This means that when multiple Detective or Judge nodes run in parallel and
    each returns a partial state, the LangGraph runtime *concatenates* their
    list updates rather than choosing one winner — preserving all evidence and
    all opinions from all parallel branches.

    Fields
    ------
    evidence_collection : Append-only list of Evidence artefacts. Written by
        Detective nodes; read by Judge nodes.
    judicial_opinions   : Append-only list of JudicialOpinion records. Written
        by Judge nodes; read by the Justice (ChiefJustice) node.
    metadata            : Mutable dict for run-level configuration (e.g.
        'repo_url', 'pdf_path', 'output_dir', 'report_path'). Not subject to
        parallel writes; only the orchestrator (main.py) writes here.
    last_updated        : UTC timestamp refreshed on every state mutation,
        useful for audit trail reconstruction.
    """

    evidence_collection: Annotated[List[Evidence], operator.add] = Field(
        default_factory=list,
        description="Append-only log of all forensic evidence gathered by Detective agents.",
    )
    judicial_opinions: Annotated[List[JudicialOpinion], operator.add] = Field(
        default_factory=list,
        description="Append-only log of all verdicts produced by Judge agents.",
    )
    metadata: dict = Field(
        default_factory=dict,
        description=(
            "Run-level key-value store for configuration and output paths. "
            "Keys used by the system: 'repo_url', 'pdf_path', 'output_dir', 'report_path'."
        ),
    )
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp of the most recent state mutation.",
    )

    def add_evidence(self, evidence: Evidence) -> None:
        """Append a validated Evidence object and refresh last_updated."""
        self.evidence_collection.append(evidence)
        self.last_updated = datetime.utcnow()

    def add_opinion(self, opinion: JudicialOpinion) -> None:
        """Append a validated JudicialOpinion object and refresh last_updated."""
        self.judicial_opinions.append(opinion)
        self.last_updated = datetime.utcnow()