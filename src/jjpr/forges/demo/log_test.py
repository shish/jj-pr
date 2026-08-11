import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.demo]

from ...conftest import run_cmd
from .log import log_cmd


class TestLog:
    def test_log_annotates_every_commit(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")

        log_output = run_cmd("jj", "pr", "log")
        assert "Test commit 1" in log_output

    def test_log_is_deterministic(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")

        # Rich assigns a random per-render `id=NNNNNN` to each hyperlink escape
        # sequence, so strip those before comparing for content equality.
        def _strip_link_ids(s: str) -> str:
            return re.sub(r"id=\d+", "id=X", s)

        first = _strip_link_ids(run_cmd("jj", "pr", "log"))
        second = _strip_link_ids(log_cmd("origin", []))
        assert first == second
