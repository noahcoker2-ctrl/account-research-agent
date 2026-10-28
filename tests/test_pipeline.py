"""End-to-end runs on saved company pages. The first two use real model replies
(Claude Sonnet, saved verbatim); the third injects typical model mistakes."""
from account_research.llm import ScriptedLLM
from account_research.pipeline import research
from account_research.report import to_markdown


def test_strong_fit_company(icp, kestrel_fetcher, kestrel_reply):
    llm = ScriptedLLM([kestrel_reply])
    r = research("kestrel-freight.example", icp, llm, kestrel_fetcher)
    assert r.fit_score == 100 and r.tier == "A" and r.coverage == 1.0
    assert r.grounding.quotes_verified == r.grounding.quotes_total == 15
    assert r.grounding.flags == []
    assert len(r.brief.buying_signals) == 4
    # The model only saw labelled sources from the company's own pages.
    prompt = llm.calls[0][1][0]["content"]
    assert "[S5] (careers)" in prompt and "Revenue Operations Manager" in prompt


def test_thin_website_scores_low_and_says_so(icp, bramble_fetcher, bramble_reply):
    r = research("bramble-studio.example", icp, ScriptedLLM([bramble_reply]), bramble_fetcher)
    verdicts = {c.criterion_id: c.verdict for c in r.brief.icp_fit}
    assert verdicts == {"b2b": "yes", "sales_team": "unclear", "growth": "unclear",
                        "revops_stack": "unclear", "region": "yes"}
    assert r.fit_score == 48 and r.tier == "C" and r.coverage == 0.35
    assert r.brief.buying_signals == []


def test_verifier_catches_injected_mistakes(icp, kestrel_fetcher, adversarial_reply):
    r = research("kestrel-freight.example", icp, ScriptedLLM([adversarial_reply]), kestrel_fetcher)
    g = r.grounding
    verdicts = {c.criterion_id: c.verdict for c in r.brief.icp_fit}
    # Paraphrased quote and made-up source id: both downgraded from yes to unclear.
    assert verdicts["growth"] == "unclear" and verdicts["revops_stack"] == "unclear"
    assert set(g.downgraded_criteria) == {"growth", "revops_stack"}
    # Near-exact quote (different case) still counts.
    assert verdicts["b2b"] == "yes"
    # Invented office and inflated number are removed; real signals stay.
    assert set(g.removed_signals) == {"Opening a Singapore office", "Hiring 10 SDRs"}
    assert len(r.brief.buying_signals) == 4
    assert g.opener_needs_review
    # Score drops from 100 to 68 (growth and revops each keep 20% credit as unclear).
    assert r.fit_score == 68 and r.tier == "B"
    md = to_markdown(r)
    assert "Needs review before sending" in md and "Removed signal 'Hiring 10 SDRs'" in md


def test_model_skipping_a_question_counts_as_unclear(icp, kestrel_fetcher, kestrel_reply):
    import json

    data = json.loads(kestrel_reply)
    data["icp_fit"] = [c for c in data["icp_fit"] if c["criterion_id"] != "region"]
    data["icp_fit"].append({"criterion_id": "made_up", "verdict": "yes", "rationale": "x", "evidence": []})
    r = research("kestrel-freight.example", icp, ScriptedLLM([json.dumps(data)]), kestrel_fetcher)
    ids = [c.criterion_id for c in r.brief.icp_fit]
    assert "made_up" not in ids and "region" in ids
    assert r.fit_score == 88  # 85 for the four answered + 20% of 15 for region
