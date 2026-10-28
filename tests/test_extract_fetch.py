from account_research.extract import extract_links, html_to_text
from account_research.fetch import classify_link, collect_pages

HTML = """<html><head><title>Acme | Home</title><script>var x = 1;</script></head>
<body><nav><a href="/about">About</a><a href="https://other.com/x">Out</a></nav>
<main><h1>Hello</h1><p>We   build   things.</p></main><footer>Footer text</footer></body></html>"""


def test_html_to_text_drops_scripts_nav_and_footer():
    title, text = html_to_text(HTML)
    assert title == "Acme | Home"
    assert "We build things." in text
    assert "var x" not in text and "Footer text" not in text and "About" not in text


def test_extract_links_keeps_same_site_only():
    links = extract_links(HTML, "https://acme.example")
    assert links == [("https://acme.example/about", "About")]


def test_classify_link():
    assert classify_link("https://a.example/careers", "") == "careers"
    assert classify_link("https://a.example/x", "Customer stories") == "customers"
    assert classify_link("https://a.example/case-studies/acme", "") == "customers"
    assert classify_link("https://a.example/blog/series-b", "") == "news"
    assert classify_link("https://a.example/legal", "Terms") is None


def test_collect_pages_finds_the_useful_pages(kestrel_fetcher):
    pages = collect_pages("kestrel-freight.example", kestrel_fetcher)
    kinds = [p.kind for p in pages]
    assert kinds[0] == "homepage"
    assert {"about", "customers", "pricing", "careers", "news"} <= set(kinds)
    assert len(pages) <= 6
    careers = next(p for p in pages if p.kind == "careers")
    assert "Revenue Operations Manager" in careers.text


def test_collect_pages_accepts_full_urls(kestrel_fetcher):
    pages = collect_pages("https://kestrel-freight.example/", kestrel_fetcher)
    assert pages[0].url == "https://kestrel-freight.example"
