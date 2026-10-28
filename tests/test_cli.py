import csv

from account_research import cli
from account_research.icp import load_icp
from account_research.fetch import FixtureFetcher
from account_research.llm import ScriptedLLM


def test_batch_ranks_accounts_and_writes_briefs(tmp_path, monkeypatch, kestrel_reply, bramble_reply):
    accounts = tmp_path / "accounts.csv"
    accounts.write_text("domain\nbramble-studio.example\nkestrel-freight.example\nmissing-site.example\n")
    out = tmp_path / "results.csv"

    def fake_build(args):
        return (load_icp(cli.Path(__file__).resolve().parent.parent / "icp.example.yaml"),
                FixtureFetcher(cli.Path(__file__).resolve().parent / "fixtures"),
                ScriptedLLM([bramble_reply, kestrel_reply], name="saved replies"))

    monkeypatch.setattr(cli, "_build", fake_build)
    assert cli.main(["batch", str(accounts), "--out", str(out)]) == 0

    rows = list(csv.DictReader(out.open()))
    assert [r["domain"] for r in rows] == ["kestrel-freight.example", "bramble-studio.example", "missing-site.example"]
    assert rows[0]["fit_score"] == "100" and rows[0]["tier"] == "A"
    assert "Could not fetch" in rows[2]["error"]
    assert (tmp_path / "results" / "kestrel-freight_example.md").exists()
