import pytest
from pydantic import ValidationError

from account_research.icp import ICP
from account_research.llm import ScriptedLLM, parse_json_reply
from account_research.pipeline import ask_model


def test_parse_json_reply_handles_fences_and_chatter():
    assert parse_json_reply('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_reply('Here you go:\n{"a": {"b": 2}}\nThanks') == {"a": {"b": 2}}
    with pytest.raises(ValueError):
        parse_json_reply("no json here")


def test_ask_model_repairs_one_bad_reply(kestrel_reply):
    llm = ScriptedLLM(["Sorry, here is a summary instead.", kestrel_reply])
    brief = ask_model(llm, "prompt")
    assert brief.company_name == "Kestrel Freight"
    assert len(llm.calls) == 2
    repair_turn = llm.calls[1][1]
    assert repair_turn[-1]["role"] == "user" and "could not be used" in repair_turn[-1]["content"]


def test_ask_model_gives_up_after_retry():
    with pytest.raises(RuntimeError):
        ask_model(ScriptedLLM(["nope", "still nope"]), "prompt")


def test_icp_weights_must_sum_to_100():
    with pytest.raises(ValidationError):
        ICP(name="x", seller="y", criteria=[{"id": "a", "question": "q", "weight": 60}])


def test_icp_ids_must_be_unique():
    with pytest.raises(ValidationError):
        ICP(name="x", seller="y", criteria=[{"id": "a", "question": "q", "weight": 50},
                                            {"id": "a", "question": "q2", "weight": 50}])
