from account_research.fetch import Page
from account_research.retrieve import Retriever, chunk_pages, select_context


def test_chunks_are_labelled_in_order_and_overlap():
    words = " ".join(f"w{i}" for i in range(250))
    chunks = chunk_pages([Page("u", "about", "t", words)], size=100, overlap=20)
    assert [c.id for c in chunks] == ["S1", "S2", "S3"]
    assert chunks[1].text.split()[0] == "w80"  # 100 - 20 overlap
    assert chunks[-1].text.split()[-1] == "w249"


def test_bm25_finds_the_careers_chunk_for_hiring_questions(kestrel_fetcher):
    from account_research.fetch import collect_pages

    chunks = chunk_pages(collect_pages("kestrel-freight.example", kestrel_fetcher))
    top = Retriever(chunks).search("hiring sales development representatives", k=1)
    assert top and top[0].kind == "careers"


def test_select_context_keeps_homepage_and_respects_budget():
    pages = [Page("h", "homepage", "", "welcome to acme analytics " * 30)]
    pages += [Page(f"p{i}", "news", "", f"topic{i} " * 120) for i in range(30)]
    chunks = chunk_pages(pages)
    picked = select_context(chunks, ["topic3", "topic7"], k_per_query=2, max_chunks=5)
    assert picked[0].kind == "homepage"
    assert len(picked) <= 5
    assert any("topic3" in c.text for c in picked)


def test_small_sites_pass_through_whole():
    pages = [Page("h", "homepage", "", "alpha"), Page("a", "about", "", "beta")]
    assert len(select_context(chunk_pages(pages), ["unrelated words"])) == 2
