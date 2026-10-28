"""Data models for the brief the model writes and the verified brief we return."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    source_id: str = Field(description="Source label such as S3")
    quote: str = Field(description="Exact words copied from that source")
    # Filled in by the verifier, never by the model.
    verified: bool = False
    match_score: float = 0.0
    problem: str = ""


class CriterionResult(BaseModel):
    criterion_id: str
    verdict: Literal["yes", "no", "unclear"]
    rationale: str
    evidence: list[Evidence] = Field(default_factory=list)


class Signal(BaseModel):
    signal: str
    why_it_matters: str
    evidence: list[Evidence] = Field(default_factory=list)


class Opener(BaseModel):
    text: str
    evidence: list[Evidence] = Field(default_factory=list)


class LLMBrief(BaseModel):
    """What the model is asked to return (as JSON)."""

    company_name: str
    company_summary: str
    summary_evidence: list[Evidence] = Field(default_factory=list)
    icp_fit: list[CriterionResult]
    buying_signals: list[Signal] = Field(default_factory=list)
    recommended_personas: list[str] = Field(default_factory=list)
    opener: Opener
    open_questions: list[str] = Field(default_factory=list)


class SourceRef(BaseModel):
    id: str
    kind: str
    url: str
    title: str


class Grounding(BaseModel):
    quotes_total: int
    quotes_verified: int
    rate: float
    flags: list[str] = Field(default_factory=list)
    removed_signals: list[str] = Field(default_factory=list)
    downgraded_criteria: list[str] = Field(default_factory=list)
    opener_needs_review: bool = False


class AccountBrief(BaseModel):
    """The final, verified output."""

    domain: str
    generated_at: str
    model: str
    brief: LLMBrief
    fit_score: int
    tier: Literal["A", "B", "C"]
    coverage: float = Field(description="Share of ICP weight answered with verified evidence")
    criteria_weights: dict[str, int]
    criteria_questions: dict[str, str]
    grounding: Grounding
    sources: list[SourceRef]
    pages_fetched: list[str]
