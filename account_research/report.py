"""Renders a verified brief as Markdown a rep can read in under a minute."""
from __future__ import annotations

from .schema import AccountBrief, Evidence

VERDICT_LABEL = {"yes": "Yes", "no": "No", "unclear": "Unclear"}


def _cite(evidence: list[Evidence]) -> str:
    if not evidence:
        return "_not found in sources_"
    good = [e for e in evidence if e.verified]
    if not good:
        return "_no verified evidence_"
    return "<br>".join(f'[{e.source_id}] "{e.quote}"' for e in good)


def to_markdown(result: AccountBrief) -> str:
    b, g = result.brief, result.grounding
    lines = [
        f"# Account brief: {b.company_name}",
        "",
        f"**{result.domain}** · Fit score **{result.fit_score}/100 (Tier {result.tier})** · "
        f"Evidence coverage **{result.coverage:.0%}** · "
        f"Grounding **{g.quotes_verified}/{g.quotes_total} quotes verified ({g.rate:.0%})** · "
        f"{result.generated_at} · model: {result.model}",
        "",
        "## Summary",
        b.company_summary,
        "",
        "## ICP fit",
        "| Criterion | Weight | Verdict | Evidence |",
        "|---|---|---|---|",
    ]
    for r in b.icp_fit:
        q = result.criteria_questions.get(r.criterion_id, r.criterion_id)
        w = result.criteria_weights.get(r.criterion_id, 0)
        verdict = VERDICT_LABEL[r.verdict]
        if r.criterion_id in g.downgraded_criteria:
            verdict += " (downgraded)"
        lines.append(f"| {q} | {w} | {verdict} | {_cite(r.evidence)} |")

    lines += ["", "## Buying signals"]
    if b.buying_signals:
        for s in b.buying_signals:
            lines.append(f"- **{s.signal}.** {s.why_it_matters} {_cite(s.evidence).replace('<br>', ' ')}")
    else:
        lines.append("- None found in the sources.")

    lines += ["", "## Suggested opener"]
    if g.opener_needs_review:
        lines.append("> **Needs review before sending.**")
        lines.append(">")
    lines.append(f"> {b.opener.text}")
    lines.append("")
    lines.append(f"Based on: {_cite(b.opener.evidence).replace('<br>', ' ')}")

    lines += ["", "## Who to contact", ", ".join(b.recommended_personas) or "Not enough information.", ""]
    lines += ["## Questions for the first call"] + [f"- {q}" for q in b.open_questions] + [""]

    lines += ["## Verification checks"]
    if g.flags:
        lines += [f"- {f}" for f in g.flags]
    else:
        lines.append("- All quotes matched their sources. No claims were removed or downgraded.")

    lines += ["", "## Sources"]
    lines += [f"- [{s.id}] {s.kind}: {s.url}" for s in result.sources]
    lines += ["", f"Pages read: {len(result.pages_fetched)}"]
    return "\n".join(lines) + "\n"
