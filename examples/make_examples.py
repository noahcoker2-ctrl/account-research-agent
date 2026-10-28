"""Regenerates the example briefs in this folder from the saved fixture pages and
the saved model replies. No API key or internet needed.

Usage: python examples/make_examples.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from account_research.fetch import FixtureFetcher
from account_research.icp import load_icp
from account_research.llm import ScriptedLLM
from account_research.pipeline import research
from account_research.report import to_markdown
from inject_mistakes import inject_mistakes

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
icp = load_icp(ROOT / "icp.example.yaml")
fetcher = FixtureFetcher(ROOT / "tests" / "fixtures")
MODEL = "claude-sonnet-5-5 (saved reply)"

runs = [
    ("kestrel-freight.example", "kestrel-freight_example", (HERE / "kestrel_model_reply.json").read_text(), MODEL),
    ("bramble-studio.example", "bramble-studio_example", (HERE / "bramble_model_reply.json").read_text(), MODEL),
    ("kestrel-freight.example", "verifier-demo_kestrel-freight",
     inject_mistakes((HERE / "kestrel_model_reply.json").read_text()), "claude-sonnet-5-5 reply with injected mistakes"),
]
for domain, stem, reply, name in runs:
    result = research(domain, icp, ScriptedLLM([reply], name=name), fetcher)
    (HERE / f"{stem}.md").write_text(to_markdown(result))
    (HERE / f"{stem}.json").write_text(result.model_dump_json(indent=2))
    g = result.grounding
    print(f"{stem}: fit {result.fit_score} (Tier {result.tier}), {g.quotes_verified}/{g.quotes_total} quotes verified")
