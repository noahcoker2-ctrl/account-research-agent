"""Prompt templates. The model only sees the selected sources, never the open web."""
from __future__ import annotations

import json

from .icp import ICP
from .retrieve import Chunk

SYSTEM = """You are a careful B2B account researcher preparing a brief for a sales rep.

Rules:
- Use ONLY the numbered sources provided. Never use outside knowledge about the company, even if you recognise it.
- Every factual claim needs evidence: the source id (for example "S3") and a quote copied word for word from that source. Quotes must be short (under 25 words) and exact, with no paraphrasing, no ellipses and no added words.
- If the sources don't answer an ICP question, use verdict "unclear" with an empty evidence list. Absence of evidence is not a "no".
- Only use verdict "no" when a source clearly contradicts the criterion.
- Buying signals must be recent or forward-looking facts from the sources (hiring, funding, expansion, new leadership, new tools). Skip generic marketing claims.
- The opener is one or two plain sentences, under 45 words, that a rep could send. It must reference one specific cited fact and connect it to what the seller offers. No flattery, no hype words, no "I noticed" or "I came across", and no claims that aren't in the sources.
- Return a single JSON object and nothing else."""

_SHAPE = {
    "company_name": "string",
    "company_summary": "2-3 sentences on what the company does and for whom",
    "summary_evidence": [{"source_id": "S1", "quote": "exact words from S1"}],
    "icp_fit": [
        {"criterion_id": "id from the ICP list", "verdict": "yes | no | unclear",
         "rationale": "one sentence", "evidence": [{"source_id": "S2", "quote": "exact words"}]}
    ],
    "buying_signals": [
        {"signal": "short label", "why_it_matters": "one sentence tied to what the seller offers",
         "evidence": [{"source_id": "S5", "quote": "exact words"}]}
    ],
    "recommended_personas": ["job titles to contact, most relevant first"],
    "opener": {"text": "the message", "evidence": [{"source_id": "S5", "quote": "exact words"}]},
    "open_questions": ["what a rep should find out on the first call that the sources don't answer"],
}


def build_user_prompt(domain: str, icp: ICP, sources: list[Chunk]) -> str:
    criteria = "\n".join(f"- {c.id}: {c.question}" for c in icp.criteria)
    personas = ", ".join(icp.personas) or "any relevant buyer"
    blocks = "\n\n".join(f"[{c.id}] ({c.kind}) {c.url}\n{c.text}" for c in sources)
    return f"""Research the company at {domain} for this seller.

What the seller offers:
{icp.seller.strip()}

ICP questions (answer every one, using these exact criterion ids):
{criteria}

Personas the seller usually sells to: {personas}

Sources:
{blocks}

Return JSON with exactly this shape:
{json.dumps(_SHAPE, indent=2)}"""


def repair_prompt(error: str) -> str:
    return (
        "Your previous reply could not be used: "
        f"{error[:400]}\nReturn only the corrected JSON object, with the same shape and rules."
    )
