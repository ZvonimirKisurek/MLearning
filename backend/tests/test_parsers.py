from datetime import datetime, timezone

import feedparser

from app.ingestion.parsers import canonicalize_url, clean_text, parse_feed_entries, parse_github_trending, url_hash

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>Paper A</title><link>https://arxiv.org/abs/2501.00001</link>
<description>arXiv:2501.00001v1 Announce Type: new Abstract: We &lt;b&gt;study&lt;/b&gt; RAG.</description>
<pubDate>Mon, 06 Jan 2025 00:00:00 GMT</pubDate></item>
<item><title></title><link>https://x.test/no-title</link></item>
<item><title>No link</title></item>
</channel></rss>"""


def test_canonicalize_strips_tracking_and_normalises():
    a = canonicalize_url("http://www.Example.com/post/?utm_source=x&b=2&a=1&fbclid=z#frag")
    assert a == "https://example.com/post?a=1&b=2"
    assert url_hash(a) == url_hash(canonicalize_url("https://example.com/post/?a=1&b=2"))


def test_canonicalize_keeps_root_path():
    assert canonicalize_url("https://example.com") == "https://example.com/"


def test_clean_text_strips_html_and_truncates_on_word_boundary():
    assert clean_text("<p>Hello  <b>world</b></p>") == "Hello world"
    out = clean_text("word " * 100, limit=20)
    assert out.endswith("…") and len(out) <= 21 and "wor…" not in out
    assert clean_text(None) == ""


def test_parse_feed_entries_skips_bad_entries_and_cleans_arxiv_prefix():
    items = parse_feed_entries(feedparser.parse(RSS), max_items=10)
    assert len(items) == 1
    assert items[0].title == "Paper A"
    assert items[0].summary == "We study RAG."
    assert items[0].published_at == datetime(2025, 1, 6, tzinfo=timezone.utc)


def test_parse_feed_respects_max_items():
    assert parse_feed_entries(feedparser.parse(RSS), max_items=0) == []


TRENDING = """<article class="Box-row"><h2><a href="/owner/repo">owner / repo</a></h2>
<p>A vector DB in Rust</p><span>1,234 stars today</span></article>
<article class="Box-row"><h2><a href="/o/no-desc">o / no-desc</a></h2></article>"""


def test_parse_github_trending():
    items = parse_github_trending(TRENDING, 10)
    assert [i.url for i in items] == ["https://github.com/owner/repo", "https://github.com/o/no-desc"]
    assert items[0].engagement == 1234 and items[0].summary == "A vector DB in Rust"
    assert items[1].title == "o/no-desc"
