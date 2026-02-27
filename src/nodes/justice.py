from src.state import AgentState, JudicialOpinion, Evidence
from typing import List, Dict
import datetime
import os
import glob


def chief_justice(state: AgentState, output_dir: str = "audit") -> str:
    """
    Synthesize Judge opinions into a final verdict.
    Generates a Markdown report with:
      - Executive Summary
      - Dissent Analysis (synthesis_rules: dissent_requirement)
      - Criterion Breakdown
      - Remediation Plan
      - Evidence Appendix (synthesis_rules: fact_supremacy)
      - Synthesis Rules Applied
    """

    if not state.judicial_opinions:
        raise ValueError("No judicial opinions found. Judges must run before synthesis.")

    os.makedirs(output_dir, exist_ok=True)

    opinions = state.judicial_opinions
    evidence = state.evidence_collection

    # -----------------------------------------------------------------------
    # Synthesis Rule: security_override
    # If any security_scan evidence has found=False, cap total score at 3
    # -----------------------------------------------------------------------
    security_override_triggered = False
    security_override_reason = ""
    for ev in evidence:
        if ev.type == "security_scan" and ev.found is False:
            security_override_triggered = True
            security_override_reason = ev.description
            break

    # -----------------------------------------------------------------------
    # Score calculation
    # -----------------------------------------------------------------------
    raw_avg = sum(op.score for op in opinions) / len(opinions) if opinions else 0.0
    if security_override_triggered:
        final_avg = min(raw_avg, 3.0)
    else:
        final_avg = raw_avg

    # -----------------------------------------------------------------------
    # 1. Executive Summary
    # -----------------------------------------------------------------------
    report_lines: List[str] = []
    report_lines.append("# LangGraph Audit Report")
    report_lines.append(f"Generated: {datetime.datetime.now().isoformat()}\n")
    report_lines.append("## Executive Summary")
    report_lines.append(f"**Overall Average Score: {final_avg:.2f} / 5.00**")
    if security_override_triggered:
        report_lines.append(
            f"\n> ⚠️ **Security Override Applied**: Score capped at 3.0 due to security finding: *{security_override_reason}*"
        )
    report_lines.append("\nJudges provided the following highlights:")
    for op in opinions:
        report_lines.append(f"- **{op.judge} ({op.criterion})** [{op.verdict}, {op.score}/5]: {op.comments}")

    # -----------------------------------------------------------------------
    # 2. Dissent Analysis (synthesis_rules: dissent_requirement)
    # Chief Justice must document where Prosecutor and Defense disagreed
    # -----------------------------------------------------------------------
    report_lines.append("\n## Dissent Analysis")
    report_lines.append(
        "_Per synthesis rules, the Chief Justice documents all Prosecutor–Defense disagreements (score diff ≥ 2)._\n"
    )

    criteria_set = list(dict.fromkeys(op.criterion for op in opinions))
    dissent_found = False
    variance_triggered_criteria = []  # for variance_re_evaluation rule

    for criterion in criteria_set:
        relevant = {op.judge: op for op in opinions if op.criterion == criterion}
        p_op = relevant.get("Prosecutor")
        d_op = relevant.get("Defense")
        tl_op = relevant.get("TechLead")
        all_scores = [op.score for op in relevant.values()]

        # variance_re_evaluation: score spread > 2 across any judges
        if all_scores and (max(all_scores) - min(all_scores)) > 2:
            variance_triggered_criteria.append(criterion)

        if p_op and d_op:
            diff = abs(p_op.score - d_op.score)
            if diff >= 2:
                dissent_found = True
                report_lines.append(f"### ⚖️ Dissent: {criterion}")
                report_lines.append(
                    f"- **Prosecutor** scored **{p_op.score}/5** — {p_op.verdict}: {p_op.comments}"
                )
                report_lines.append(
                    f"- **Defense** scored **{d_op.score}/5** — {d_op.verdict}: {d_op.comments}"
                )
                if criterion in variance_triggered_criteria:
                    report_lines.append(
                        f"  > ⚠️ **Variance Re-Evaluation Triggered**: score spread of {max(all_scores) - min(all_scores)} exceeds threshold of 2. "
                        f"Evidence cited by each judge should be re-examined before accepting final score."
                    )
                report_lines.append(
                    f"- *Score divergence: {diff} points. Chief Justice notes this criterion as contested.*\n"
                )

    if not dissent_found:
        report_lines.append("_No significant dissent (score diff ≥ 2) between Prosecutor and Defense on any criterion._\n")

    # -----------------------------------------------------------------------
    # 3. Criterion Breakdown (with functionality_weight for graph_orchestration)
    # -----------------------------------------------------------------------
    report_lines.append("\n## Criterion Breakdown")

    for criterion in criteria_set:
        relevant_ops = [op for op in opinions if op.criterion == criterion]
        # functionality_weight: TechLead carries highest weight for graph_orchestration
        crit_id = next(
            (op.judge for op in relevant_ops if op.criterion == criterion), ""
        )
        # Find the dimension id for this criterion name
        from utils.config_loader import load_rubric
        rubric = load_rubric()
        dim_id = next(
            (d["id"] for d in rubric.get("dimensions", []) if d["name"] == criterion), None
        )
        if dim_id == "graph_orchestration":
            # TechLead vote carries double weight
            weighted_scores = []
            for op in relevant_ops:
                weight = 2 if op.judge == "TechLead" else 1
                weighted_scores.extend([op.score] * weight)
            avg_crit_score = sum(weighted_scores) / len(weighted_scores) if weighted_scores else 0
            weight_note = " *(TechLead weighted ×2 per functionality_weight rule)*"
        else:
            avg_crit_score = sum(op.score for op in relevant_ops) / len(relevant_ops)
            weight_note = ""
        report_lines.append(f"\n### {criterion}{weight_note}")
        report_lines.append(f"- **Average Score**: {avg_crit_score:.2f} / 5.00")
        if criterion in variance_triggered_criteria:
            report_lines.append(f"- ⚠️ **High Variance** — score spread exceeds 2 points, re-evaluation recommended")
        for op in relevant_ops:
            report_lines.append(f"\n#### {op.judge} — {op.verdict} ({op.score}/5)")
            report_lines.append(f"{op.rationale}")

    # -----------------------------------------------------------------------
    # 4. Remediation Plan
    # -----------------------------------------------------------------------
    report_lines.append("\n## Remediation Plan")
    remediation_added = False
    for op in opinions:
        if op.score < 5:
            report_lines.append(
                f"- **[{op.judge} on {op.criterion}]**: {op.comments}"
            )
            remediation_added = True
    if not remediation_added:
        report_lines.append("_No remediations required. All criteria scored 5/5._")

    # -----------------------------------------------------------------------
    # 5. Evidence Appendix (synthesis_rules: fact_supremacy)
    # "Forensic evidence (facts) always overrules Judicial opinion"
    # -----------------------------------------------------------------------
    report_lines.append("\n## Evidence Appendix")
    report_lines.append(
        "_Per synthesis rules (fact_supremacy), raw detective findings are preserved here as the authoritative forensic record._\n"
    )

    if not evidence:
        report_lines.append("_No evidence collected._")
    else:
        # Group by source
        sources: Dict[str, List[Evidence]] = {}
        for ev in evidence:
            sources.setdefault(ev.source, []).append(ev)

        for source_name, items in sources.items():
            report_lines.append(f"### {source_name}")
            for ev in items:
                status = "✅" if ev.found else ("❌" if ev.found is False else "ℹ️")
                report_lines.append(f"\n**{status} [{ev.type}]** — {ev.description}")
                if ev.goal:
                    report_lines.append(f"- *Goal*: {ev.goal}")
                if ev.location:
                    report_lines.append(f"- *Location*: `{ev.location}`")
                if ev.rationale:
                    report_lines.append(f"- *Rationale*: {ev.rationale}")
                if ev.content:
                    snippet = str(ev.content)[:400]
                    report_lines.append(f"- *Snippet*:\n```\n{snippet}\n```")
                report_lines.append(f"- *Confidence*: {ev.confidence:.0%}")

    # -----------------------------------------------------------------------
    # 6. Synthesis Rules Applied
    # -----------------------------------------------------------------------
    report_lines.append("\n## Synthesis Rules Applied")

    rules_applied = []
    if security_override_triggered:
        rules_applied.append(
            f"- ✅ **security_override**: Score capped at 3.0. Reason: {security_override_reason}"
        )
    else:
        rules_applied.append("- ✔️ **security_override**: Not triggered (no confirmed security failures).")

    rules_applied.append(
        "- ✅ **fact_supremacy**: Evidence Appendix rendered above; detective findings take precedence over judicial interpretation."
    )

    if dissent_found:
        rules_applied.append(
            "- ✅ **dissent_requirement**: Prosecutor–Defense disagreements documented in Dissent Analysis section."
        )
    else:
        rules_applied.append(
            "- ✔️ **dissent_requirement**: No significant dissent detected; section included for transparency."
        )

    rules_applied.append(
        "- ✅ **functionality_weight**: TechLead score weighted ×2 for the 'Graph Orchestration Architecture' criterion."
    )

    if variance_triggered_criteria:
        rules_applied.append(
            f"- ⚠️ **variance_re_evaluation**: Triggered for criterion(s): {', '.join(variance_triggered_criteria)}. "
            "Score spread > 2 — these criteria have been flagged for forensic re-examination."
        )
    else:
        rules_applied.append(
            "- ✔️ **variance_re_evaluation**: Not triggered (no criterion had score spread > 2)."
        )

    report_lines.extend(rules_applied)

    # -----------------------------------------------------------------------
    # Write report
    # -----------------------------------------------------------------------
    report_content = "\n".join(report_lines)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(output_dir, f"final_audit_report_{timestamp}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

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