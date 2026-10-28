import httpx

from account_research.fetch import HttpFetcher, fetch_news

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Kestrel Freight raises Series B - Example News</title><link>https://news.example/1</link>
<pubDate>Wed, 04 Mar 2026 09:00:00 GMT</pubDate></item>
<item><title>Second headline</title><link>https://news.example/2</link><pubDate>Thu, 05 Mar 2026</pubDate></item>
</channel></rss>"""


class FakeFetcher:
    def __init__(self, body):
        self.body, self.urls = body, []

    def get(self, url):
        self.urls.append(url)
        return self.body


def test_fetch_news_parses_headlines():
    f = FakeFetcher(RSS)
    pages = fetch_news("Kestrel Freight", f, limit=1)
    assert len(pages) == 1 and pages[0].kind == "news headline"
    assert "raises Series B" in pages[0].text and "2026" in pages[0].text
    assert "%22Kestrel+Freight%22" in f.urls[0]


def test_fetch_news_survives_bad_xml():
    assert fetch_news("X", FakeFetcher("<html>not rss")) == []


def _fetcher(status):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(status, text="User-agent: *\nDisallow: /private")
        return httpx.Response(200, text="<html><body>ok</body></html>")
    f = HttpFetcher()
    f.client = httpx.Client(transport=httpx.MockTransport(handler))
    return f


def test_robots_rules_are_respected():
    f = _fetcher(200)
    assert f.get("https://site.example/") is not None
    assert f.get("https://site.example/private/page") is None


def test_missing_robots_allows_but_server_error_blocks():
    assert _fetcher(404).get("https://site.example/private") is not None
    assert _fetcher(503).get("https://site.example/") is None
