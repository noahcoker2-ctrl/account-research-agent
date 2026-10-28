import sys
from pathlib import Path

import pytest

from account_research.fetch import FixtureFetcher
from account_research.icp import load_icp

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
EXAMPLES = ROOT / "examples"
sys.path.insert(0, str(EXAMPLES))
from inject_mistakes import inject_mistakes  # noqa: E402


@pytest.fixture
def icp():
    return load_icp(ROOT / "icp.example.yaml")


@pytest.fixture
def kestrel_fetcher():
    return FixtureFetcher(FIXTURES / "kestrel-freight.example")


@pytest.fixture
def bramble_fetcher():
    return FixtureFetcher(FIXTURES / "bramble-studio.example")


@pytest.fixture
def kestrel_reply():
    """A real reply from Claude Sonnet for the Kestrel fixture, saved verbatim."""
    return (EXAMPLES / "kestrel_model_reply.json").read_text()


@pytest.fixture
def bramble_reply():
    """A real reply from Claude Sonnet for the Bramble fixture (wrapped in a ```json fence)."""
    return (EXAMPLES / "bramble_model_reply.json").read_text()


@pytest.fixture
def adversarial_reply(kestrel_reply):
    """The Kestrel reply with deliberate mistakes a model can make, to test the verifier."""
    return inject_mistakes(kestrel_reply)
