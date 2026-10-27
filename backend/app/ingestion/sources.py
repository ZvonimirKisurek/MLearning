from pathlib import Path

import yaml

from app.ingestion.models import SourceSpec


def load_sources(path: str | Path) -> list[SourceSpec]:
    """Load + validate the YAML catalogue. Raises on schema errors or duplicate slugs."""
    raw = yaml.safe_load(Path(path).read_text())
    specs = [SourceSpec.model_validate(entry) for entry in raw["sources"]]
    seen: set[str] = set()
    for s in specs:
        if s.slug in seen:
            raise ValueError(f"duplicate source slug: {s.slug}")
        seen.add(s.slug)
    return specs
