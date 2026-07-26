import json
from pathlib import Path

from ...conftest import run_cmd
from .list import list_cmd


class TestList:
    def test_list_returns_demo_data(self, clone: Path):
        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        list_cmd("origin")
        assert len(js) > 0
        assert {item["cr_id"] for item in js} == {"#101", "#102", "#103", "#104"}
        # Demonstrates a range of states, checks, and blockers.
        states = {item["state"]["name"] for item in js}
        assert "Accepted" in states
        assert "Blocked" in states
        assert any(item["checks"] for item in js)
        assert any(item["blockers"] for item in js)
