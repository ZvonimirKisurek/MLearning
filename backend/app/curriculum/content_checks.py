"""Deterministic checks on LLM-written long-form text. Each returns a list of PROBLEMS (empty list = acceptable).

Why code-level checks on prose? A prompt can ask for "at least 1,500 words" or "valid Python"; nothing guarantees the
model complied. These checks turn each requirement into a measurement, and the repair loop feeds the exact problem
back ("your chapter has 1,212 words of prose; the minimum is 1,500"), which is far more effective than hoping.
They also cap what the model can get wrong without us noticing: invented links, citations to articles that were
never shown, and Python examples that do not even parse.
"""
from __future__ import annotations

import ast
import re

_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9_'’\-]*")
_FENCE = re.compile(r"^```([^\n`]*)\n(.*?)^```[ \t]*$", re.S | re.M)
_CITE = re.compile(r"\[(A\d+)\]")
_URL = re.compile(r"(?:https?://([^\s/)\]>\"']+))|(?:\bwww\.)", re.I)
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "[::1]")
_BULLET = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
_MATH = re.compile(r"\$\$.+?\$\$|(?<![\w$])\$[^$\n]+\$(?!\w)", re.S)


def strip_code(md: str) -> str:
    """The markdown without fenced code blocks (so word counts measure teaching prose, not code)."""
    return _FENCE.sub("", md)


def count_words(md: str, *, include_code: bool = False) -> int:
    return len(_WORD.findall(md if include_code else strip_code(md)))


def external_urls(text: str) -> list[str]:
    """URLs other than localhost-style addresses, which commands legitimately contain (curl http://localhost:8000)."""
    bad = []
    for m in _URL.finditer(text):
        host = (m.group(1) or "www.").lower()
        if not host.startswith(_LOCAL_HOSTS):
            bad.append(m.group(0))
    return bad


def citation_problems(text: str, article_ids: frozenset[str] | set[str] | None, min_citations: int = 0) -> list[str]:
    cited = set(_CITE.findall(text))
    problems = []
    if article_ids is not None:
        unknown = sorted(cited - set(article_ids))
        if unknown:
            problems.append(f"cites unknown article ids {unknown}; only cite ids that appear in <articles>, written like [A3]")
        if len(cited & set(article_ids)) < min_citations:
            problems.append(f"cites {len(cited & set(article_ids))} distinct supplied articles; at least {min_citations} required (write [A3] after the claim)")
    return problems


def python_syntax_problems(md: str) -> list[str]:
    problems = []
    for i, (lang, code) in enumerate(_FENCE.findall(md), start=1):
        if lang.strip().lower() in ("python", "py", "python3"):
            try:
                ast.parse(code)
            except SyntaxError as exc:
                problems.append(f"python code block #{i} has a syntax error at line {exc.lineno}: {exc.msg}. Fix it, or use a ```bash block for shell/notebook commands")
    return problems


def check_prose(text: str, *, min_words: int, max_words: int | None = None, article_ids=None, min_citations: int = 0, max_bullets: int = 2) -> list[str]:
    """Essay-style prose: length window, no links, real citations, mostly paragraphs (not bullet lists)."""
    problems = []
    n = count_words(text)
    if n < min_words:
        problems.append(f"only {n} words; the minimum is {min_words}. Expand with more analysis, not filler")
    if max_words and n > max_words:
        problems.append(f"{n} words; the maximum is {max_words}. Tighten it")
    if external_urls(text):
        problems.append("contains URLs; never write links (cite supplied articles as [A3])")
    problems += citation_problems(text, article_ids, min_citations)
    bullets = sum(1 for line in text.splitlines() if _BULLET.match(line))
    if bullets > max_bullets:
        problems.append(f"{bullets} bullet/numbered lines; this must be continuous prose in paragraphs (at most {max_bullets} list lines)")
    return problems


def check_chapter(md: str, *, min_words: int, article_ids=None) -> list[str]:
    """A textbook chapter: enough prose, real structure, valid code, math, grounded citations, no links."""
    problems = []
    n = count_words(md)
    if n < min_words:
        problems.append(f"the chapter has {n} words of prose (code excluded); the minimum is {min_words}. "
                        f"Add at least {min_words - n + 150} words: deepen the explanations, add a worked example, intuition and pitfalls, then return the COMPLETE chapter")
    if len(re.findall(r"^```", md, re.M)) % 2:
        problems.append("a code fence is never closed (unbalanced ``` lines)")
    if re.search(r"^# \S", md, re.M):
        problems.append("do not use a level-1 heading (# ...): the title is shown separately; use ## for sections")
    if len(re.findall(r"^## \S", md, re.M)) < 6:
        problems.append("use at least 6 sections, each starting with a '## ' heading")
    if not re.search(r"^##\s+.*(check your understanding|self-test|exercises)", md, re.M | re.I):
        problems.append("end with a '## Check Your Understanding' section containing 4-6 questions")
    langs = [lang.strip().lower() for lang, _ in _FENCE.findall(md)]
    if sum(1 for lang in langs if lang in ("python", "py", "python3")) < 2:
        problems.append("include at least 2 fenced ```python code examples that are complete enough to run")
    if not _MATH.search(strip_code(md)):
        problems.append("include the key mathematics: inline $...$ and display $$...$$ LaTeX with an intuition for each formula")
    if external_urls(md):
        problems.append("contains URLs; never write links (cite supplied articles as [A3])")
    problems += citation_problems(md, article_ids, min_citations=1 if article_ids else 0)
    problems += python_syntax_problems(md)
    return problems


def check_essay(md: str, *, min_words: int, max_words: int, article_ids=None) -> list[str]:
    problems = check_prose(md, min_words=min_words, max_words=max_words, article_ids=article_ids, min_citations=2 if article_ids and len(article_ids) >= 2 else 0)
    if len([p for p in re.split(r"\n\s*\n", md.strip()) if p.strip()]) < 4:
        problems.append("write at least 4 paragraphs separated by blank lines")
    if re.search(r"^#{1,2} \S", md, re.M):
        problems.append("do not use level-1/2 headings; the headline is shown separately (### sub-headings are allowed)")
    return problems
