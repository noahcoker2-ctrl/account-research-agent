"""Turns raw HTML into clean readable text and a list of links."""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# Elements that carry no useful company information.
_DROP = ["script", "style", "noscript", "svg", "iframe", "form", "nav", "footer", "header"]


def html_to_text(html: str) -> tuple[str, str]:
    """Return (title, text). Navigation, footers and scripts are removed."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    for tag in soup(_DROP):
        tag.decompose()
    body = soup.body or soup
    text = body.get_text("\n", strip=True)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return title, text.strip()


def extract_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """Return (absolute_url, anchor_text) for links on the same site."""
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(base_url).netloc.removeprefix("www.")
    seen, links = set(), []
    for a in soup.find_all("a", href=True):
        url = urljoin(base_url, a["href"]).split("#")[0].rstrip("/")
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            continue
        if parsed.netloc.removeprefix("www.") != host:
            continue
        if url in seen:
            continue
        seen.add(url)
        links.append((url, a.get_text(" ", strip=True)))
    return links
