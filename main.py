import argparse
import os
import sys
from src.state import AgentState, Evidence, JudicialOpinion
from src.graph import StateGraph, Node
from src.nodes.detectives import RepoInvestigator, DocAnalyst, VisionInspector
from src.nodes.judges import Prosecutor, Defense, TechLead
from src.nodes.justice import chief_justice
from utils.config_loader import get_test_repo_url, load_rubric

def build_audit_graph():
    """Build the LangGraph for auditing with parallel fan-out and conditional routing."""
    builder = StateGraph()

    # ------------------------------------------------------------------
    # 1. Detective Nodes (Fan-Out)
    # ------------------------------------------------------------------

    def repo_node(state: AgentState) -> AgentState:
        """RepoInvestigator node with deep AST analysis."""
        repo_url = state.metadata.get("repo_url", ".")
        investigator = RepoInvestigator(repo_url=repo_url)
        
        # 1. Basic Git History
        try:
            commits = investigator.collect_git_commits()
            sha = investigator.collect_current_sha()
            state.add_evidence(Evidence(
                source="RepoInvestigator", type="git_log",
                goal="Check git history", found=True,
                description=f"Found {len(commits)} commits.",
                location=f"repo:{repo_url} HEAD:{sha}",
                rationale="History confirms active development.",
                confidence=1.0
            ))
        except Exception:
            state.add_evidence(Evidence(
                source="RepoInvestigator", type="missing_artifact",
                goal="Check git history", found=False,
                description="Git history unavailable.",
                confidence=0.0
            ))

        # 2. Deep AST: State Schema Verification (Pydantic)
        try:
            state_info = investigator.collect_state_info()
            pydantic_classes = state_info.get("classes", [])
            has_pydantic = "pydantic" in str(state_info.get("imports", [])).lower()
            state.add_evidence(Evidence(
                source="RepoInvestigator", type="ast_parse",
                goal="Verify Pydantic usage", found=len(pydantic_classes) > 0,
                description=f"Identified state classes: {pydantic_classes}",
                location="src/state.py",
                rationale="Architecture requires typed Pydantic models for AgentState.",
                content=f"Imports: {state_info.get('imports')}",
                confidence=1.0
            ))
        except Exception as e:
            print(f"[RepoDetective] AST Error: {e}")

        # 3. Deep AST: Graph Topology Verification (StateGraph)
        try:
            graph_info = investigator.collect_graph_info()
            has_stategraph = "StateGraph" in graph_info.get("classes", [])
            state.add_evidence(Evidence(
                source="RepoInvestigator", type="ast_parse",
                goal="Verify StateGraph orchestration", found=has_stategraph,
                description="StateGraph class definition located.",
                location="src/graph.py",
                rationale="Orchestration must be handled by a structured StateGraph.",
                content=f"Classes found: {graph_info.get('classes')}",
                confidence=1.0
            ))
        except Exception:
            pass

        # 4. Forensic: Tool Safety & Sandboxing Verification
        try:
            safety_info = investigator.collect_tool_safety_info()
            state.add_evidence(Evidence(
                source="RepoInvestigator", type="security_scan",
                goal="Verify sandboxed git operations", 
                found=safety_info.get("has_sandboxing") and safety_info.get("has_prompt_guard"),
                description=f"Sandboxing: {safety_info.get('has_sandboxing')}, Prompt Guard: {safety_info.get('has_prompt_guard')}",
                location="src/tools/git_tools.py",
                rationale="Security compliance requires GIT_TERMINAL_PROMPT=0 and temporary directories.",
                content=f"Security Metrics: {safety_info.get('snippet', '')}",
                confidence=1.0
            ))
        except Exception:
            pass

        # 5. Forensic: Judicial Nuance & Prompt Verification
        try:
            nuance_info = investigator.collect_judicial_nuance_info()
            state.add_evidence(Evidence(
                source="RepoInvestigator", type="prompt_analysis",
                goal="Verify persona distinctness & JSON intent", 
                found=nuance_info.get("has_persona_logic") and nuance_info.get("json_intent"),
                description=f"Persona Logic: {nuance_info.get('has_persona_logic')}, JSON Intent: {nuance_info.get('json_intent')}",
                location="src/nodes/judges.py",
                rationale="Audit integrity requires distinct judge personas and structured outputs.",
                content=f"Prompt Logic: {nuance_info.get('logic_snippets', {})}",
                confidence=1.0
            ))
        except Exception:
            pass

        return state

    def doc_node(state: AgentState) -> AgentState:
        """Analyze documentation for theoretical depth and artifact claims."""
        pdf_path = state.metadata.get("pdf_path", "report/AUDIT_SUBMISSION_REPORT.md")
        analyst = DocAnalyst(pdf_path)
        
        # 1. Theoretical Depth (Dialectical Synthesis, Metacognition)
        try:
            summary = analyst.check_keywords(["Dialectical Synthesis", "Metacognition"])
            for kw, data in summary.items():
                state.add_evidence(Evidence(
                    source="DocAnalyst", type="theoretical_verification",
                    goal=f"Verify mention of '{kw}'", found=data["hit_count"] > 0,
                    description=f"Found '{kw}' {data['hit_count']} times on pages {data['page_numbers']}.",
                    location=pdf_path,
                    rationale="Architecture report must demonstrate theoretical alignment with MAS principles.",
                    content=str(data["contexts"][:2]),
                    confidence=1.0 if data["hit_count"] > 0 else 0.0
                ))
        except Exception:
            pass

        # 2. File Path Verification (Forensic Proof of Existence)
        try:
            found, missing = analyst.verify_file_paths()
            state.add_evidence(Evidence(
                source="DocAnalyst", type="file_verification",
                goal="Verify artifact existence", found=len(found) > 0,
                description=f"Verified {len(found)} files; {len(missing)} missing.",
                location=pdf_path,
                rationale="Forensic audit must prove documented files exist in the repo.",
                content=f"Verified paths: {found[:10]}",
                confidence=1.0
            ))
        except Exception:
            pass
        
        return state

    def vision_node(state: AgentState) -> AgentState:
        """VisionInspector node."""
        img_path = state.metadata.get("image_path", "")
        if not img_path:
            state.add_evidence(Evidence(source="VisionInspector", type="skipped", 
                                        description="No image path provided.", confidence=0.0))
            return state
        
        inspector = VisionInspector(img_path)
        classification = inspector.classify()
        state.add_evidence(Evidence(source="VisionInspector", type="vision_scan",
                                   description=f"Classified as {classification.get('label')}",
                                   confidence=0.8))
        return state

    # ------------------------------------------------------------------
    # 2. Aggregation & Conflict Resolution (Fan-In)
    # ------------------------------------------------------------------

    def aggregator_node(state: AgentState) -> AgentState:
        """
        Consolidates evidence from all detectives.
        Cleans duplicates or inconsistencies before judges see it.
        """
        print("[*] EvidenceAggregator: Consolidating forensic findings...")
        # Note: In our current StateGraph, the results from parallel nodes 
        # are concatenated at the graph level. This node can perform additional
        # semantic cleanup if needed.
        return state

    # ------------------------------------------------------------------
    # 3. Judges (Intelligence Layer)
    # ------------------------------------------------------------------

    def judge_node(state: AgentState):
        """Judges: Prosecutor, Defense, and TechLead evaluation layer."""
        print(f"[*] Judges: Evaluating {len(state.evidence_collection)} pieces of evidence...")
        proc, defen, lead = Prosecutor(), Defense(), TechLead()
        
        # Build a high-fidelity evidence context for the Judges
        evidence_segments = []
        for e in state.evidence_collection:
            segment = [
                f"### Source: {e.source} ({e.type})",
                f"**Goal**: {e.goal or 'Not specified'}",
                f"**Finding**: {e.description}",
            ]
            if e.location:
                segment.append(f"**Location**: {e.location}")
            if e.content:
                # Cap content to prevent token bloat
                clean_content = str(e.content)[:1000]
                segment.append(f"**Forensic Snippet**:\n```\n{clean_content}\n```")
            evidence_segments.append("\n".join(segment))
            
        evidence_str = "\n\n---\n\n".join(evidence_segments)
        
        rubric = load_rubric()
        for i, dim in enumerate(rubric.get("dimensions", []), 1):
            dim_id = dim["id"]
            print(f"    -> Evaluating Dimension {i}/{len(rubric.get('dimensions', []))}: {dim_id}")
            # Judges now receive the full breadcrumb trail
            state.add_opinion(proc.evaluate_dimension(dim_id, evidence_str))
            state.add_opinion(defen.evaluate_dimension(dim_id, evidence_str))
            state.add_opinion(lead.evaluate_dimension(dim_id, evidence_str))
            
        return state

    # ------------------------------------------------------------------
    # 4. Failure / Warning Handler (Conditional Routing)
    # ------------------------------------------------------------------

    def low_confidence_node(state: AgentState):
        """Executed if aggregate confidence is critically low."""
        print("[!] Warning: Critical evidence gaps detected. Adding warning to state.")
        state.metadata["critical_warning"] = "Audit proceeds with low confidence evidence."
        return state

    # ------------------------------------------------------------------
    # 5. Justice (Synthesis)
    # ------------------------------------------------------------------

    def justice_node(state: AgentState):
        """Justice: Final report synthesis."""
        report_path = chief_justice(state, output_dir=state.metadata.get("output_dir", "audit"))
        state.metadata["report_path"] = report_path
        return state

    # ------------------------------------------------------------------
    # Graph Topology Configuration
    # ------------------------------------------------------------------

    # Add Nodes
    builder.add_node(Node("RepoDetective",    repo_node),  start=True)
    builder.add_node(Node("DocDetective",     doc_node),   start=True)
    builder.add_node(Node("VisionDetective",  vision_node), start=True)
    builder.add_node(Node("EvidenceAggregator", aggregator_node))
    builder.add_node(Node("LowConfidenceHandler", low_confidence_node))
    builder.add_node(Node("Judges",           judge_node))
    builder.add_node(Node("Justice",          justice_node))

    # Static Edges (Fan-In)
    builder.add_edge("RepoDetective",   "EvidenceAggregator")
    builder.add_edge("DocDetective",    "EvidenceAggregator")
    builder.add_edge("VisionDetective", "EvidenceAggregator")

    # Conditional Edge for Failures
    def route_after_aggregation(state: AgentState) -> str:
        # If any essential detective found=False with high weight, route to handler
        avg_conf = sum(e.confidence for e in state.evidence_collection) / max(1, len(state.evidence_collection))
        if avg_conf < 0.3:
            return "failure"
        return "success"

    builder.add_conditional_edge(
        "EvidenceAggregator",
        route_after_aggregation,
        {"failure": "LowConfidenceHandler", "success": "Judges"}
    )
    
    # LowConfidenceHandler also routes to Judges eventually
    builder.add_edge("LowConfidenceHandler", "Judges")
    builder.add_edge("Judges", "Justice")

    return builder


def main():
    parser = argparse.ArgumentParser(description="LangGraph Auditor CLI")
    parser.add_argument("--mode", choices=["peer", "self"], required=True, help="Evaluation mode")
    args = parser.parse_args()

    state = AgentState()
    # Initialise metadata if needed (already has default_factory=dict)

    if args.mode == "peer":
        print("[*] Running Peer Evaluation...")
        repo_url = get_test_repo_url()
        if not repo_url or "github.com" not in repo_url:
            print("[!] Error: Peer mode requires a valid TEST_REPO_URL in .env")
            sys.exit(1)
        state.metadata["repo_url"] = repo_url
        state.metadata["output_dir"] = "audit/report_on_peer_generated"
    else:
        print("[*] Running Self Evaluation...")
        from utils.config_loader import get_self_repo_url
        self_url = get_self_repo_url()
        state.metadata["repo_url"] = self_url if self_url else "."
        state.metadata["pdf_path"] = "report/Report.pdf"
        state.metadata["output_dir"] = "audit/report_on_self_generated"

    graph = build_audit_graph()
    final_state = graph.run(state)
    
    print(f"[*] Audit complete. Report generated at: {final_state.metadata.get('report_path')}")

if __name__ == "__main__":
    main()
