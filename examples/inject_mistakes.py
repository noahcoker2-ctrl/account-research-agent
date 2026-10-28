"""Injects the mistakes language models typically make into a real model reply,
to show (and test) that the verifier catches each one."""
import json


def inject_mistakes(reply: str) -> str:
    data = json.loads(reply)
    for crit in data["icp_fit"]:
        if crit["criterion_id"] == "growth":  # a paraphrase instead of a quote
            crit["evidence"] = [{"source_id": "S6", "quote": "The company raised 40 million euros in new funding"}]
        if crit["criterion_id"] == "revops_stack":  # cites a source that doesn't exist
            crit["evidence"] = [{"source_id": "S9", "quote": "You will own our Salesforce instance"}]
        if crit["criterion_id"] == "b2b":  # a real quote with different capitalisation (should still pass)
            crit["evidence"] = [{"source_id": "S2", "quote": "WE SELL OUR PLATFORM TO LOGISTICS AND SUPPLY CHAIN TEAMS"}]
    data["buying_signals"] += [
        {"signal": "Opening a Singapore office", "why_it_matters": "New region.",  # invented fact
         "evidence": [{"source_id": "S2", "quote": "We are opening an office in Singapore next year"}]},
        {"signal": "Hiring 10 SDRs", "why_it_matters": "Big sales expansion.",  # inflated number, real quote
         "evidence": [{"source_id": "S5", "quote": "Sales Development Representative (3 openings) - Lyon or Amsterdam"}]},
    ]
    data["opener"]["evidence"] = []  # opener with nothing behind it
    return json.dumps(data)
