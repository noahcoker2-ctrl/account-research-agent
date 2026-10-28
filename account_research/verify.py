"""Checks the model's work against the sources before anyone sees it.

1. Every quote must come from a real source id and appear in that source word
   for word. Only case, spacing, punctuation and quote marks may differ, so a
   changed word or number fails the check.
2. Numbers in a claim (headcount, funding, number of roles) must appear in
   one of the claim's verified quotes, which means they appear in the source.
3. Anything that fails is downgraded, removed or flagged, never silently kept.
"""
from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz

from .retrieve import Chunk
from .schema import Evidence, Grounding, LLMBrief

_TOKEN = re.compile(r"[a-z0-9]+|[\u20ac$\u00a3%]")  # words, numbers and currency / percent signs


def tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text).lower()
    return _TOKEN.findall(text)


def check_quote(quote: str, source_text: str) -> tuple[bool, float]:
    """True if the quote's words appear, in order and unchanged, in the source.

    Returns (verified, similarity). Similarity is a 0-100 fuzzy score kept only
    as a diagnostic, to show how close a failed quote came.
    """
    q, t = tokens(quote), tokens(source_text)
    if len(q) < 2:  # a single word proves nothing ("yes", "B2B")
        return False, 0.0
    if f" {' '.join(q)} " in f" {' '.join(t)} ":
        return True, 100.0
    return False, float(fuzz.partial_ratio(" ".join(q), " ".join(t)))


_NUM = re.compile(r"(?<![\w.])[$€£]?\d[\d,.]*(?:\s?(?:%|k|m|bn|million|billion))?", re.I)


def numbers_in(text: str) -> set[str]:
    out = set()
    for m in _NUM.findall(text):
        digits = re.sub(r"[^\d.]", "", m).rstrip(".")
        if digits:
            out.add(digits)
    return out


def numbers_supported(claim: str, quotes: list[str]) -> bool:
    needed = numbers_in(claim)
    if not needed:
        return True
    available = set().union(*(numbers_in(q) for q in quotes)) if quotes else set()
    return needed <= available


def _verify_evidence(evidence: list[Evidence], sources: dict[str, Chunk]) -> list[Evidence]:
    for ev in evidence:
        src = sources.get(ev.source_id.strip("[] "))
        if src is None:
            ev.verified, ev.match_score, ev.problem = False, 0.0, f"unknown source {ev.source_id}"
            continue
        ok, score = check_quote(ev.quote, src.text)
        ev.verified, ev.match_score = ok, score
        ev.problem = "" if ok else f"quote not found in {ev.source_id}"
    return evidence


def verified_quotes(evidence: list[Evidence]) -> list[str]:
    return [e.quote for e in evidence if e.verified]


def verify_brief(brief: LLMBrief, sources: list[Chunk]) -> tuple[LLMBrief, Grounding]:
    by_id = {c.id: c for c in sources}
    flags: list[str] = []
    downgraded: list[str] = []

    all_evidence: list[Evidence] = []

    _verify_evidence(brief.summary_evidence, by_id)
    all_evidence += brief.summary_evidence
    summary_quotes = verified_quotes(brief.summary_evidence)
    if not summary_quotes:
        flags.append("Company summary has no verified quote; treat it as unconfirmed.")
    elif not numbers_supported(brief.company_summary, summary_quotes):
        flags.append("Company summary contains a number that its quotes don't support.")

    for crit in brief.icp_fit:
        _verify_evidence(crit.evidence, by_id)
        all_evidence += crit.evidence
        good = verified_quotes(crit.evidence)
        if crit.verdict in ("yes", "no") and not good:
            downgraded.append(crit.criterion_id)
            flags.append(f"ICP '{crit.criterion_id}': '{crit.verdict}' had no verifiable evidence, changed to 'unclear'.")
            crit.verdict = "unclear"
        elif not numbers_supported(crit.rationale, good):
            flags.append(f"ICP '{crit.criterion_id}': the rationale states a number its quotes don't support.")

    kept, removed = [], []
    for sig in brief.buying_signals:
        _verify_evidence(sig.evidence, by_id)
        all_evidence += sig.evidence
        good = verified_quotes(sig.evidence)
        if not good:
            removed.append(sig.signal)
            flags.append(f"Removed signal '{sig.signal}': no verifiable evidence.")
        elif not numbers_supported(sig.signal + " " + sig.why_it_matters, good):
            removed.append(sig.signal)
            flags.append(f"Removed signal '{sig.signal}': it states a number its quotes don't support.")
        else:
            kept.append(sig)
    brief.buying_signals = kept

    _verify_evidence(brief.opener.evidence, by_id)
    all_evidence += brief.opener.evidence
    opener_good = verified_quotes(brief.opener.evidence)
    opener_review = False
    if not opener_good:
        opener_review = True
        flags.append("Opener is not backed by a verified quote; review before sending.")
    elif not numbers_supported(brief.opener.text, opener_good):
        opener_review = True
        flags.append("Opener mentions a number its quotes don't support; review before sending.")
    if len(brief.opener.text.split()) > 60:
        opener_review = True
        flags.append("Opener is longer than 60 words.")

    total = len(all_evidence)
    ok = sum(e.verified for e in all_evidence)
    for e in all_evidence:
        if not e.verified:
            flags.append(f"Unverified quote ({e.problem}): \"{e.quote[:80]}\"")

    # De-duplicate flags while keeping order.
    flags = list(dict.fromkeys(flags))
    return brief, Grounding(
        quotes_total=total,
        quotes_verified=ok,
        rate=round(ok / total, 3) if total else 0.0,
        flags=flags,
        removed_signals=removed,
        downgraded_criteria=downgraded,
        opener_needs_review=opener_review,
    )
