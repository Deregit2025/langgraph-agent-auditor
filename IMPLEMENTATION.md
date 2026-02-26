# Project Implementation & Reproduction Guide

This document provides a technical deep-dive into the architectural decisions and implementation details of the LangGraph Auditor. It is intended for engineers who wish to understand the forensic logic or recreate the multi-agent swarm.

## 🏗️ Graph Topology: Fan-Out / Fan-In

The system uses a custom `StateGraph` (defined in `src/graph.py`) that implements a classic Map-Reduce pattern:

1.  **Parallel Fan-Out**: Detective nodes originate as parallel entry points. Each node is provided a deep-copy of the state to prevent concurrent write races.
2.  **Evidence Aggregator**: A central node that acts as a synchronization barrier.
3.  **Dialectical Judges**: A second fan-out level where Prosecutor, Defense, and Tech Lead personas evaluate findings.
4.  **Synthesis**: The Chief Justice compiles the final Markdown report.

## 🛡️ Forensic Layer: AST Discovery

Instead of relying on fragile regex, the `RepoInvestigator` utilizes Python's `ast` module to perform high-fidelity code analysis.

- **Pydantic Verification**: Parses `src/state.py` to ensure that all models inherit from `BaseModel` and utilize `Annotated` types for reducers.
- **Topology Check**: Scans `src/graph.py` to identify `add_node` and `add_edge` calls, reconstructing the real-world graph structure for audit.

## 📊 State Management: CRDT-Lite Semantics

The `AgentState` (defined in `src/state.py`) handles parallel updates using Pydantic combined with functional reducers:

```python
class AgentState(BaseModel):
    evidence_collection: Annotated[List[Evidence], operator.add] = Field(default_factory=list)
    judicial_opinions: Annotated[List[JudicialOpinion], operator.add] = Field(default_factory=list)
```

- **`operator.add`**: Ensures that when parallel nodes return results, the lists are concatenated (merged) rather than one overwriting the other.
- **Type Safety**: Runtime validation ensures that only valid `Evidence` and `JudicialOpinion` objects are stored in the state.

## ⚖️ Intelligence Layer: Preventing Persona Collusion

To prevent "Persona Collusion" (where agents simply agree with each other), we implement distinct, adversarial system prompts for each judge:

- **Prosecutor**: Instructed to hunt for security negligence, orchestration fraud, and missing validations.
- **Defense**: Directed to highlight creative solutions (like AST parsing) and support simpler designs that prioritize robust Pydantic validation.
- **Tech Lead**: Focused on technical feasibility, state reducer correctness, and architectural scalability.

## 🚀 Reproduction Guide

To recreate this system, follow these steps:

1.  **Dependency Alignment**: Ensure Python 3.11+ is used. The `poetry.lock` file contains the exact versions of `langgraph`, `pydantic`, and `docling` required.
2.  **Environment Setup**: Define `LLM_PROVIDER` (OpenAI or Google) and provide the respective API keys in a `.env` file.
3.  **Rubric Configuration**: The `rubric/rubric.json` file is the "brain" of the audit. Ensure it contains the specific `criterion_ids` and `judicial_logic` for your target audit.
4.  **Execution**: Run `main.py --mode self` to initiate the audit trace.
5.  **Forensic Proof**: Check `audit/langsmith_logs/` for the JSONL trace files which provide the proof of parallel node execution.
