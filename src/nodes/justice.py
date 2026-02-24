from src.state import AgentState, JudicialOpinion
from typing import List
import datetime
import os
import glob

# ------------------------------
# ChiefJusticeNode
# ------------------------------
def chief_justice(state: AgentState, output_dir: str = "audit") -> str:
    """
    Synthesize Judge opinions into a final verdict.
    Generates a Markdown report with:
      - Executive Summary
      - Criterion Breakdown
      - Remediation Plan
    """

    if not state.judicial_opinions:
        raise ValueError("No judicial opinions found. Judges must run before synthesis.")

    # Ensure output folder exists
    os.makedirs(output_dir, exist_ok=True)

    # Executive Summary
    exec_summary_lines: List[str] = []
    exec_summary_lines.append(f"# LangGraph Audit Report")
    exec_summary_lines.append(f"Generated: {datetime.datetime.now().isoformat()}\n")
    exec_summary_lines.append("## Executive Summary")
    avg_score = sum(op.score for op in state.judicial_opinions) / len(state.judicial_opinions)
    exec_summary_lines.append(f"Overall Average Score: {avg_score:.2f}\n")
    exec_summary_lines.append("Judges provided the following highlights:")
    for op in state.judicial_opinions:
        exec_summary_lines.append(f"- **{op.judge} ({op.criterion})**: {op.comments}")

    # Criterion Breakdown
    breakdown_lines: List[str] = ["\n## Criterion Breakdown"]
    criteria_seen = set()
    for op in state.judicial_opinions:
        if op.criterion not in criteria_seen:
            criteria_seen.add(op.criterion)
            relevant_ops = [j for j in state.judicial_opinions if j.criterion == op.criterion]
            avg_crit_score = sum(j.score for j in relevant_ops) / len(relevant_ops)
            breakdown_lines.append(f"### {op.criterion}")
            breakdown_lines.append(f"- Average Score: {avg_crit_score:.2f}")
            for j in relevant_ops:
                breakdown_lines.append(f"  - {j.judge}: {j.score}, Comments: {j.comments}")

    # Remediation Plan
    remediation_lines: List[str] = ["\n## Remediation Plan"]
    for op in state.judicial_opinions:
        if op.score < 5:
            remediation_lines.append(f"- {op.criterion} issues identified by {op.judge}: {op.comments}")

    # Combine all sections
    report_lines = exec_summary_lines + breakdown_lines + remediation_lines
    report_content = "\n".join(report_lines)

    # Save report with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(output_dir, f"final_audit_report_{timestamp}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    # Save as latest_report.md
    latest_path = os.path.join(output_dir, "latest_report.md")
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    # Purge old reports: keep only the 5 most recent timestamped ones
    report_files = glob.glob(os.path.join(output_dir, "final_audit_report_*.md"))
    report_files.sort(key=os.path.getmtime, reverse=True)
    
    for old_file in report_files[5:]:
        try:
            os.remove(old_file)
        except Exception as e:
            print(f"[Justice] Warning: Could not delete old report {old_file}: {e}")

    print(f"[ChiefJustice] Report generated at: {report_path}")
    print(f"[ChiefJustice] Latest report updated at: {latest_path}")
    return latest_path