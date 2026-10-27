"""Pure parsing / normalisation helpers (no I/O) so they are trivially unit-testable."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from app.ingestion.models import RawItem

_TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src", "igshid", "cmpid", "source"}
_ARXIV_PREFIX = re.compile(r"^arXiv:\S+\s+Announce Type:\s*\S+\s+Abstract:\s*", re.I)


def canonicalize_url(url: str) -> str:
    """Normalise so the same page maps to one string: https, no www, no fragment/tracking params, sorted query."""
    p = urlsplit(url.strip())
    host = p.netloc.lower().removeprefix("www.")
    query = sorted(
        (k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
    )
    path = p.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, urlencode(query), ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def clean_text(html: str | None, limit: int = 1200) -> str:
    """Strip markup, collapse whitespace, drop arXiv boilerplate, truncate on a word boundary."""
    if not html:
        return ""
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    text = _ARXIV_PREFIX.sub("", re.sub(r"\s+", " ", text).strip())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def _entry_datetime(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def parse_feed_entries(parsed, max_items: int) -> list[RawItem]:
    """feedparser result -> RawItems. Skips entries lacking a title or link."""
    items: list[RawItem] = []
    for entry in parsed.entries[:max_items]:
        title = clean_text(entry.get("title"), 300)
        link = entry.get("link")
        if not title or not link:
            continue
        body = entry.get("summary") or (entry.get("content") or [{}])[0].get("value")
        items.append(RawItem(
            title=title,
            url=link,
            summary=clean_text(body),
            author=entry.get("author"),
            published_at=_entry_datetime(entry),
        ))
    return items


def parse_github_trending(html: str, max_items: int) -> list[RawItem]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[RawItem] = []
    for row in soup.select("article.Box-row")[:max_items]:
        a = row.select_one("h2 a")
        if not a or not a.get("href"):
            continue
        repo = a["href"].strip("/")
        p_tag = row.select_one("p")
        desc = clean_text(p_tag.get_text(" ")) if p_tag else ""
        stars = None
        m = re.search(r"([\d,]+)\s+stars?\s+(today|this week|this month)", row.get_text(" ", strip=True))
        if m:
            stars = int(m.group(1).replace(",", ""))
        items.append(RawItem(
            title=f"{repo}: {desc}" if desc else repo,
            url=f"https://github.com/{repo}",
            summary=desc,
            published_at=datetime.now(timezone.utc),
            engagement=stars,
            metadata={"repo": repo},
        ))
    return items
