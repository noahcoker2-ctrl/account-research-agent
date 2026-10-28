"""Loads the ideal customer profile (ICP) that the agent scores against."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class Criterion(BaseModel):
    id: str
    question: str
    weight: int = Field(ge=0, le=100)


class ICP(BaseModel):
    name: str
    seller: str = Field(description="One or two sentences on what you sell, used for the opener")
    criteria: list[Criterion]
    signal_queries: list[str] = Field(default_factory=list)
    personas: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _weights_sum_to_100(self) -> "ICP":
        total = sum(c.weight for c in self.criteria)
        if total != 100:
            raise ValueError(f"criteria weights must sum to 100, got {total}")
        ids = [c.id for c in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("criteria ids must be unique")
        return self


def load_icp(path: str | Path) -> ICP:
    return ICP.model_validate(yaml.safe_load(Path(path).read_text()))
