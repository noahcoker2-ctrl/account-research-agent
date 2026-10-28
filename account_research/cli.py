"""Command line interface.

  python -m account_research research acme.com --icp icp.example.yaml
  python -m account_research batch accounts.csv --icp icp.example.yaml --out results.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .fetch import FixtureFetcher, HttpFetcher
from .icp import load_icp
from .llm import DEFAULT_MODEL, AnthropicLLM, ScriptedLLM
from .pipeline import research
from .report import to_markdown


def _build(args):
    icp = load_icp(args.icp)
    fetcher = FixtureFetcher(args.fixtures) if args.fixtures else HttpFetcher()
    if args.scripted:
        llm = ScriptedLLM([Path(args.scripted).read_text()] * 2, name=f"{args.model} (saved reply)")
    else:
        llm = AnthropicLLM(model=args.model)
    return icp, fetcher, llm


def _save(result, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = result.domain.replace(".", "_")
    (out_dir / f"{stem}.json").write_text(result.model_dump_json(indent=2))
    md = out_dir / f"{stem}.md"
    md.write_text(to_markdown(result))
    return md


def cmd_research(args) -> int:
    icp, fetcher, llm = _build(args)
    result = research(args.domain, icp, llm, fetcher, include_news=args.news, max_pages=args.max_pages)
    md = _save(result, Path(args.out))
    g = result.grounding
    print(f"{result.brief.company_name}: fit {result.fit_score}/100 (Tier {result.tier}), "
          f"{g.quotes_verified}/{g.quotes_total} quotes verified, {len(g.flags)} flags -> {md}")
    return 0


def cmd_batch(args) -> int:
    icp, fetcher, llm = _build(args)
    out_dir = Path(args.out).with_suffix("")
    rows = []
    with open(args.csv, newline="") as f:
        domains = [r["domain"].strip() for r in csv.DictReader(f) if r.get("domain", "").strip()]
    for domain in domains:
        try:
            r = research(domain, icp, llm, fetcher, include_news=args.news, max_pages=args.max_pages)
            md = _save(r, out_dir)
            rows.append({
                "domain": domain, "company": r.brief.company_name, "fit_score": r.fit_score, "tier": r.tier,
                "grounding_rate": r.grounding.rate,
                "top_signal": r.brief.buying_signals[0].signal if r.brief.buying_signals else "",
                "opener": r.brief.opener.text, "needs_review": r.grounding.opener_needs_review,
                "brief": str(md), "error": "",
            })
            print(f"ok   {domain}: {r.fit_score}/100")
        except Exception as err:  # keep going: one bad site shouldn't stop the batch
            rows.append({"domain": domain, "error": str(err)[:200]})
            print(f"fail {domain}: {err}", file=sys.stderr)
    fields = ["domain", "company", "fit_score", "tier", "grounding_rate", "top_signal", "opener",
              "needs_review", "brief", "error"]
    rows.sort(key=lambda r: -(r.get("fit_score") or -1))
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {args.out}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="account_research", description="Grounded account research briefs.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--icp", default="icp.example.yaml", help="ICP definition (YAML)")
        sp.add_argument("--model", default=DEFAULT_MODEL, help="Anthropic model id")
        sp.add_argument("--news", action="store_true", help="also read recent news headlines")
        sp.add_argument("--max-pages", type=int, default=6)
        sp.add_argument("--fixtures", help="read pages from a folder of saved HTML instead of the web")
        sp.add_argument("--scripted", help="use a saved model reply (JSON file) instead of calling the API")

    r = sub.add_parser("research", help="research one company")
    r.add_argument("domain")
    r.add_argument("--out", default="briefs")
    common(r)
    r.set_defaults(func=cmd_research)

    b = sub.add_parser("batch", help="research every domain in a CSV with a 'domain' column")
    b.add_argument("csv")
    b.add_argument("--out", default="results.csv")
    common(b)
    b.set_defaults(func=cmd_batch)

    args = p.parse_args(argv)
    return args.func(args)
