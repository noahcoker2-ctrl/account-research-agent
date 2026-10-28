"""End-to-end research: fetch -> chunk -> retrieve -> model -> verify -> score."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import ValidationError

from .fetch import Fetcher, collect_pages, fetch_news
from .icp import ICP
from .llm import LLM, parse_json_reply
from .prompts import SYSTEM, build_user_prompt, repair_prompt
from .retrieve import Chunk, chunk_pages, select_context
from .schema import AccountBrief, CriterionResult, LLMBrief, SourceRef
from .verify import verify_brief

VERDICT_CREDIT = {"yes": 1.0, "unclear": 0.2, "no": 0.0}


def fit_score(results: list[CriterionResult], icp: ICP) -> int:
    """Weighted ICP score from the verified verdicts. Computed in code, not by the model."""
    by_id = {r.criterion_id: r for r in results}
    total = 0.0
    for c in icp.criteria:
        verdict = by_id[c.id].verdict if c.id in by_id else "unclear"
        total += c.weight * VERDICT_CREDIT[verdict]
    return round(total)


def coverage(results: list[CriterionResult], icp: ICP) -> float:
    """Share of the ICP weight answered with a verified yes or no (how much we actually know)."""
    answered = {r.criterion_id for r in results if r.verdict in ("yes", "no")}
    return round(sum(c.weight for c in icp.criteria if c.id in answered) / 100, 2)


def tier_for(score: int) -> str:
    return "A" if score >= 75 else "B" if score >= 55 else "C"


def ask_model(llm: LLM, user_prompt: str, retries: int = 1) -> LLMBrief:
    """Call the model, validate the JSON, and ask it to fix its reply once if needed."""
    messages = [{"role": "user", "content": user_prompt}]
    last_error = ""
    for _ in range(retries + 1):
        reply = llm.complete(SYSTEM, messages)
        try:
            return LLMBrief.model_validate(parse_json_reply(reply))
        except (ValueError, ValidationError) as err:
            last_error = str(err)
            messages = messages + [
                {"role": "assistant", "content": reply},
                {"role": "user", "content": repair_prompt(last_error)},
            ]
    raise RuntimeError(f"Model did not return a valid brief: {last_error[:300]}")


def research(
    domain: str,
    icp: ICP,
    llm: LLM,
    fetcher: Fetcher,
    *,
    include_news: bool = False,
    max_pages: int = 6,
    max_sources: int = 18,
) -> AccountBrief:
    pages = collect_pages(domain, fetcher, max_pages=max_pages)
    if include_news:
        company_guess = pages[0].title.split("|")[0].split(" - ")[0].strip() or domain
        pages += fetch_news(company_guess, fetcher)

    chunks = chunk_pages(pages)
    queries = [c.question for c in icp.criteria] + icp.signal_queries + [
        "what the company does products services customers",
    ]
    sources: list[Chunk] = select_context(chunks, queries, max_chunks=max_sources)

    brief = ask_model(llm, build_user_prompt(domain, icp, sources))

    # Keep only ICP answers for known criteria, and add "unclear" for any the model skipped.
    known = {c.id for c in icp.criteria}
    answered = {r.criterion_id for r in brief.icp_fit}
    brief.icp_fit = [r for r in brief.icp_fit if r.criterion_id in known]
    for c in icp.criteria:
        if c.id not in answered:
            brief.icp_fit.append(CriterionResult(criterion_id=c.id, verdict="unclear",
                                                 rationale="The model did not answer this question."))

    brief, grounding = verify_brief(brief, sources)
    score = fit_score(brief.icp_fit, icp)

    return AccountBrief(
        domain=domain,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        model=llm.name,
        brief=brief,
        fit_score=score,
        tier=tier_for(score),
        coverage=coverage(brief.icp_fit, icp),
        criteria_weights={c.id: c.weight for c in icp.criteria},
        criteria_questions={c.id: c.question for c in icp.criteria},
        grounding=grounding,
        sources=[SourceRef(id=c.id, kind=c.kind, url=c.url, title=c.title) for c in sources],
        pages_fetched=[p.url for p in pages],
    )
