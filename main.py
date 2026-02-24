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
    """Build the LangGraph for auditing."""
    builder = StateGraph()
    
    # Define Nodes
    # Detectives
    def repo_node(state: AgentState):
        repo_url = state.metadata.get("repo_url", ".")
        investigator = RepoInvestigator(repo_url=repo_url)
        commits = investigator.collect_git_commits()
        state.add_evidence(Evidence(source="RepoInvestigator", type="git_log", description=f"Found {len(commits)} commits"))
        return state

    def doc_node(state: AgentState):
        pdf_path = state.metadata.get("pdf_path", "audit/report_example.pdf")
        if os.path.exists(pdf_path):
            analyst = DocAnalyst(pdf_path=pdf_path)
            keywords = analyst.check_keywords()
            state.add_evidence(Evidence(source="DocAnalyst", type="pdf_scan", description=f"Found keywords: {list(keywords.keys())}"))
        return state

    # Judges
    def judge_node(state: AgentState):
        proc = Prosecutor()
        defen = Defense()
        lead = TechLead()
        
        # Collect all evidence into a string for LLM/Heuristic consumption
        evidence_str = "\n".join([f"- {e.source} ({e.type}): {e.description}" for e in state.evidence_collection])
        
        # Evaluate each dimension in the rubric
        rubric = load_rubric()
        for dim in rubric.get("dimensions", []):
            dim_id = dim["id"]
            state.add_opinion(proc.evaluate_dimension(dim_id, evidence_str))
            state.add_opinion(defen.evaluate_dimension(dim_id, evidence_str))
            state.add_opinion(lead.evaluate_dimension(dim_id, evidence_str))
        
        return state

    # Justice
    def justice_node(state: AgentState):
        output_dir = state.metadata.get("output_dir", "audit")
        report_path = chief_justice(state, output_dir=output_dir)
        state.metadata["report_path"] = report_path
        return state

    # Add Nodes to Graph
    builder.add_node(Node("Detectives", lambda s: doc_node(repo_node(s))), start=True)
    builder.add_node(Node("Judges", judge_node))
    builder.add_node(Node("Justice", justice_node))
    
    # Add Edges
    builder.add_edge("Detectives", "Judges")
    builder.add_edge("Judges", "Justice")
    
    return builder

def main():
    parser = argparse.ArgumentParser(description="LangGraph Auditor CLI")
    parser.add_argument("--mode", choices=["peer", "self"], required=True, help="Evaluation mode")
    args = parser.parse_args()

    state = AgentState()
    state.metadata = {} # Add metadata field to state dynamically if not in model

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
