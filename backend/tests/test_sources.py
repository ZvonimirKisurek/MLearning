import pytest

from app.ingestion.fetchers import FETCHERS
from app.ingestion.models import SourceSpec
from app.ingestion.sources import load_sources

SPECS = load_sources("sources/sources.yaml")


def test_catalogue_has_100_plus_sources_across_all_categories():
    assert len(SPECS) >= 100
    assert {s.category for s in SPECS} == {"research", "industry_news", "engineering_blog", "community", "newsletter", "researcher"}


def test_every_kind_has_a_fetcher_and_required_config():
    for s in SPECS:
        assert s.kind in FETCHERS
        if s.kind == "reddit":
            assert s.config.get("subreddit"), s.slug
        if s.kind == "hackernews":
            assert s.config.get("query"), s.slug


def test_urls_are_unique_https():
    assert all(s.url.startswith("https://") for s in SPECS)
    non_hn = [s.url for s in SPECS if s.kind != "hackernews"]  # HN sources share a base URL by design
    assert len(non_hn) == len(set(non_hn))


def test_invalid_slug_rejected():
    with pytest.raises(ValueError):
        SourceSpec(slug="Bad Slug", name="x", category="research", url="https://x.test")
