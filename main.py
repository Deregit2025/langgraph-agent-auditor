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
        """RepoInvestigator node."""
        repo_url = state.metadata.get("repo_url", ".")
        investigator = RepoInvestigator(repo_url=repo_url)
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
        return state

    def doc_node(state: AgentState) -> AgentState:
        """DocAnalyst node."""
        pdf_path = state.metadata.get("pdf_path", "report/AUDIT_SUBMISSION_REPORT.md")
        if not os.path.exists(pdf_path):
            state.add_evidence(Evidence(
                source="DocAnalyst", type="missing_artifact",
                goal="Locate PDF", found=False,
                description=f"File {pdf_path} not found.",
                confidence=0.0
            ))
            return state
        
        analyst = DocAnalyst(pdf_path=pdf_path)
        keywords = analyst.check_keywords()
        matches = [kw for kw, info in keywords.items() if info["hit_count"] > 0]
        state.add_evidence(Evidence(
            source="DocAnalyst", type="pdf_scan",
            goal="Verify terminology", found=len(matches) > 0,
            description=f"Found keywords: {matches}",
            location=pdf_path,
            confidence=0.9
        ))
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
        """Judges: Prosecutor, Defense, and TechLead."""
        proc, defen, lead = Prosecutor(), Defense(), TechLead()
        evidence_str = "\n".join([f"- {e.source}: {e.description}" for e in state.evidence_collection])
        rubric = load_rubric()
        for dim in rubric.get("dimensions", []):
            dim_id = dim["id"]
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
        state.metadata["output_dir"] = "audit/report_on_self_generated"

    graph = build_audit_graph()
    final_state = graph.run(state)
    
    print(f"[*] Audit complete. Report generated at: {final_state.metadata.get('report_path')}")

if __name__ == "__main__":
    main()
