import json
from dataclasses import asdict

import httpx

from . import cr


class TestBlocker:
    def test_rich_with_color_and_url(self) -> None:
        url = httpx.URL("https://example.com")
        b = cr.Check(name="Blocker1", state=cr.CheckState.FAIL, url=url)
        rich_output = b.__rich__()
        assert "[red]" in rich_output
        assert "[link=https://example.com]" in rich_output


class TestState:
    def test_str(self) -> None:
        s = cr.ReviewState(name="Open", color="green")
        assert "Open" in str(s)


class TestCodeReview:
    def test_asdict_with_extra(self) -> None:
        code_review = cr.CodeReview(
            cr_id="456",
            title="Fix bug",
            url=httpx.URL("https://example.com/fix-bug"),
            state=cr.ReviewState(name="Open", color="blue"),
            checks=[],
            extra={"author": "alice", "branch": "feature/x"},
        )

        result = asdict(code_review)
        assert result["extra"]["author"] == "alice"
        assert result["extra"]["branch"] == "feature/x"

    def test_json(self) -> None:
        code_review = cr.CodeReview(
            cr_id="456",
            title="Fix bug",
            url=httpx.URL("https://example.com/fix-bug"),
            state=cr.ReviewState(name="Open", color="blue"),
            checks=[],
            extra={"author": "alice", "branch": "feature/x"},
        )

        result = json.dumps(asdict(code_review), default=cr.json_default)
        assert '"author": "alice"' in result
        assert '"branch": "feature/x"' in result
        assert '"https://example.com/fix-bug"' in result
