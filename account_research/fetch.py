"""Collects a company's own pages (and optionally recent news headlines).

The agent only reads public pages: the homepage plus the most useful pages it
links to (about, customers, pricing, careers, blog or press). It respects
robots.txt and identifies itself with a clear user agent.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib import robotparser
from urllib.parse import quote_plus, urlparse

import httpx

from .extract import extract_links, html_to_text

USER_AGENT = "AccountResearchAgent/1.0 (portfolio project; respects robots.txt)"

# Which pages are worth reading, in priority order, and the words that identify them.
PAGE_KINDS: dict[str, list[str]] = {
    "about": ["about", "company", "who-we-are", "our-story", "team"],
    "customers": ["customers", "case-studies", "case-study", "stories", "clients"],
    "pricing": ["pricing", "plans"],
    "careers": ["careers", "jobs", "join-us", "hiring", "work-with-us"],
    "news": ["blog", "news", "press", "newsroom", "announcement"],
    "product": ["product", "platform", "features", "solutions", "services"],
}


@dataclass
class Page:
    url: str
    kind: str
    title: str
    text: str


class Fetcher(Protocol):
    def get(self, url: str) -> str | None:
        """Return the response body, or None if the page can't be fetched."""


class HttpFetcher:
    """Fetches live pages over HTTPS, honouring robots.txt."""

    def __init__(self, timeout: float = 15.0):
        self.client = httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT})
        self._robots: dict[str, robotparser.RobotFileParser] = {}

    def _allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        if root not in self._robots:
            # RFC 9309: a 4xx robots.txt means no rules; a 5xx or no answer means stay out.
            rp = robotparser.RobotFileParser()
            try:
                resp = self.client.get(f"{root}/robots.txt")
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                elif 400 <= resp.status_code < 500:
                    rp.parse([])
                else:
                    rp.parse(["User-agent: *", "Disallow: /"])
            except httpx.HTTPError:
                rp.parse(["User-agent: *", "Disallow: /"])
            self._robots[root] = rp
        return self._robots[root].can_fetch(USER_AGENT, url)

    def get(self, url: str) -> str | None:
        if not self._allowed(url):
            return None
        try:
            resp = self.client.get(url)
        except httpx.HTTPError:
            return None
        if resp.status_code != 200:
            return None
        return resp.text


class FixtureFetcher:
    """Serves saved HTML files instead of the internet (tests and offline demos).

    https://example.com/ -> <dir>/index.html, https://example.com/careers -> <dir>/careers.html
    (or <dir>/example.com/index.html when <dir> holds several sites).
    """

    def __init__(self, directory: str | Path):
        self.dir = Path(directory)

    def get(self, url: str) -> str | None:
        parsed = urlparse(url)
        # Accept either one site's folder, or a folder holding one sub-folder per domain.
        base = self.dir / parsed.netloc if (self.dir / parsed.netloc).is_dir() else self.dir
        path = parsed.path.strip("/") or "index"
        file = base / f"{path}.html"
        return file.read_text() if file.exists() else None


def classify_link(url: str, anchor: str) -> str | None:
    path = urlparse(url).path.lower()
    text = anchor.lower()
    for kind, words in PAGE_KINDS.items():
        if any(w in path or w in text for w in words):
            return kind
    return None


def collect_pages(domain: str, fetcher: Fetcher, max_pages: int = 6) -> list[Page]:
    """Fetch the homepage and up to max_pages - 1 of its most useful linked pages."""
    domain = domain.strip().lower().removeprefix("https://").removeprefix("http://").strip("/")
    home_url = f"https://{domain}"
    html = fetcher.get(home_url)
    if html is None:
        raise RuntimeError(f"Could not fetch {home_url}")
    title, text = html_to_text(html)
    pages = [Page(home_url, "homepage", title, text)]

    chosen: dict[str, str] = {}
    for url, anchor in extract_links(html, home_url):
        kind = classify_link(url, anchor)
        if kind and kind not in chosen and url.rstrip("/") != home_url:
            chosen[kind] = url

    for kind in PAGE_KINDS:  # priority order
        if len(pages) >= max_pages:
            break
        url = chosen.get(kind)
        if not url:
            continue
        body = fetcher.get(url)
        if body:
            t, x = html_to_text(body)
            if x:
                pages.append(Page(url, kind, t, x))
    return pages


def fetch_news(company: str, fetcher: Fetcher, limit: int = 5) -> list[Page]:
    """Recent headlines from Google News RSS. Headlines only, so claims stay modest."""
    url = f"https://news.google.com/rss/search?q={quote_plus(chr(34) + company + chr(34))}&hl=en-US&gl=US&ceid=US:en"
    body = fetcher.get(url)
    if not body:
        return []
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    pages = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        date = (item.findtext("pubDate") or "").strip()
        if title:
            pages.append(Page(link, "news headline", title, f"{title} (published {date})"))
        if len(pages) >= limit:
            break
    return pages
