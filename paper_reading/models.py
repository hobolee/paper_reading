from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Paper:
    id: str
    source: str
    title: str
    authors: list[str] = field(default_factory=list)
    published: str = ""
    updated: str = ""
    abstract: str = ""
    url: str = ""
    pdf_url: str = ""
    doi: str = ""
    journal: str = ""
    categories: list[str] = field(default_factory=list)
    image_url: str = ""
    keyword_matches: list[str] = field(default_factory=list)
    score: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)

    def match_text(self) -> str:
        parts = [
            self.title,
            self.abstract,
            self.journal,
            self.source,
            " ".join(self.categories),
            " ".join(self.authors),
        ]
        return "\n".join(part for part in parts if part)

    def stable_key(self) -> str:
        if self.doi:
            return f"doi:{self.doi.lower()}"
        return self.id.lower()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
