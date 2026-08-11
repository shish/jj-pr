import json
from pathlib import Path

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.gerrit]

from ...conftest import run_cmd, tmp_cwd


class TestDownload:
    def test_download(self, clone: Path, repo: httpx.URL):
        # Upload a change from the first clone
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "upload")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        change_num = js[0]["cr_id"].lstrip("c")

        # Download the change in a fresh clone and verify the file is present
        with tmp_cwd() as clone2:
            run_cmd("jj", "git", "clone", str(repo), ".")
            run_cmd("jj", "pr", "download", change_num)
            assert (clone2 / "test_file.txt").exists()
            assert (clone2 / "test_file.txt").read_text() == "Test content"
