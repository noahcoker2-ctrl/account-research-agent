from account_research.retrieve import Chunk
from account_research.schema import Evidence, LLMBrief
from account_research.verify import check_quote, numbers_in, numbers_supported, verify_brief

SRC = "Today we are a team of 240 people across Amsterdam, Lyon and Chicago. We raised a €40 million Series B."


def test_exact_quote_is_verified():
    assert check_quote("a team of 240 people across Amsterdam", SRC) == (True, 100.0)


def test_case_spacing_and_quote_marks_are_ignored():
    ok, _ = check_quote("TODAY  we are a team of 240 people", SRC)
    assert ok
    ok, _ = check_quote("\u201cWe raised a \u20ac40 million Series B.\u201d", SRC)
    assert ok


def test_paraphrase_is_rejected():
    ok, score = check_quote("the company employs roughly 240 staff in three cities", SRC)
    assert not ok and score < 100


def test_changed_numbers_and_words_are_rejected():
    for altered in ["a team of 400 people across Amsterdam", "We raised a \u20ac90 million Series B",
                    "We raised a \u20ac40 million Series C", "We raised a $40 million Series B",
                    "a team of 240 people across Amsterdam, Paris"]:
        ok, score = check_quote(altered, SRC)
        assert not ok, altered
        assert score > 80  # close, which is exactly why a fuzzy match isn't enough


def test_tiny_quotes_prove_nothing():
    assert check_quote("Lyon", SRC) == (False, 0.0)


def test_numbers_are_extracted_and_compared():
    assert numbers_in("Raised €40M, 3 openings, 4,000+ carriers") == {"40", "3", "4000"}
    assert numbers_supported("Hiring 3 SDRs", ["Sales Development Representative (3 openings)"])
    assert not numbers_supported("Hiring 10 SDRs", ["Sales Development Representative (3 openings)"])
    assert numbers_supported("No numbers here", [])


def _brief(**over):
    base = {
        "company_name": "Acme",
        "company_summary": "Acme has 240 people.",
        "summary_evidence": [{"source_id": "S1", "quote": "a team of 240 people across Amsterdam"}],
        "icp_fit": [{"criterion_id": "growth", "verdict": "yes", "rationale": "r",
                     "evidence": [{"source_id": "S1", "quote": "We raised a €40 million Series B"}]}],
        "buying_signals": [],
        "opener": {"text": "Hi", "evidence": [{"source_id": "S1", "quote": "We raised a €40 million Series B"}]},
    }
    base.update(over)
    return LLMBrief.model_validate(base)


SOURCES = [Chunk("S1", "u", "about", "t", SRC)]


def test_clean_brief_passes_with_no_flags():
    brief, g = verify_brief(_brief(), SOURCES)
    assert g.quotes_verified == g.quotes_total == 3 and g.rate == 1.0
    assert g.flags == [] and not g.opener_needs_review


def test_yes_without_verified_evidence_is_downgraded():
    brief, g = verify_brief(_brief(icp_fit=[{"criterion_id": "growth", "verdict": "yes", "rationale": "r",
                                             "evidence": [{"source_id": "S7", "quote": "We raised a lot"}]}]), SOURCES)
    assert brief.icp_fit[0].verdict == "unclear"
    assert g.downgraded_criteria == ["growth"]
    assert any("unknown source S7" in f for f in g.flags)


def test_no_verdict_also_needs_evidence():
    brief, g = verify_brief(_brief(icp_fit=[{"criterion_id": "growth", "verdict": "no", "rationale": "r"}]), SOURCES)
    assert brief.icp_fit[0].verdict == "unclear"


def test_signal_with_unsupported_number_is_removed():
    sig = {"signal": "Grew to 500 people", "why_it_matters": "x",
           "evidence": [{"source_id": "S1", "quote": "a team of 240 people across Amsterdam"}]}
    brief, g = verify_brief(_brief(buying_signals=[sig]), SOURCES)
    assert brief.buying_signals == []
    assert g.removed_signals == ["Grew to 500 people"]


def test_rationale_with_unsupported_number_is_flagged():
    crit = [{"criterion_id": "growth", "verdict": "yes", "rationale": "Raised 90 million euros",
             "evidence": [{"source_id": "S1", "quote": "We raised a \u20ac40 million Series B"}]}]
    brief, g = verify_brief(_brief(icp_fit=crit), SOURCES)
    assert brief.icp_fit[0].verdict == "yes"
    assert any("rationale states a number" in f for f in g.flags)


def test_opener_without_evidence_needs_review():
    _, g = verify_brief(_brief(opener={"text": "Congrats on the round", "evidence": []}), SOURCES)
    assert g.opener_needs_review


def test_evidence_objects_record_why_they_failed():
    brief, _ = verify_brief(_brief(summary_evidence=[{"source_id": "S1", "quote": "a team of 900 people in Paris"}]),
                            SOURCES)
    ev: Evidence = brief.summary_evidence[0]
    assert not ev.verified and ev.problem == "quote not found in S1"
