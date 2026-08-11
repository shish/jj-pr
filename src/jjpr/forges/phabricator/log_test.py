from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.phabricator]

from ...conftest import run_cmd


class TestLog:
    def test_log(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "upload")

        log_output = run_cmd("jj", "pr", "log")
        assert "Test commit 1" in log_output
        assert "Needs Review" in log_output
