from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np


@dataclass
class Skill:
    slug: str
    name: str
    level: float  # 0-100
    target: float
    description: str
    embedding: np.ndarray | None = None

    @property
    def gap(self) -> float:
        """Fraction of the way still to go to target, in [0, 1]."""
        return max(0.0, min(1.0, (self.target - self.level) / max(self.target, 1.0)))


@dataclass
class Candidate:
    """A recent canonical article, with its embedding, eligible for the prompt."""

    id: str  # uuid
    title: str
    summary: str
    url: str
    published_at: datetime
    source_slug: str
    source_name: str
    category: str
    source_weight: float
    engagement: int | None
    embedding: np.ndarray


@dataclass
class RankedArticle:
    short_id: str  # "A1".. - the only handle the LLM ever sees
    candidate: Candidate
    score: float
    nearest_skill: str
    similarity: float
