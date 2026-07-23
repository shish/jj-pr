import json
import re
from pathlib import Path

from ...conftest import run_cmd
from .forge import Demo


class TestMeta:
    def test_meta(self, tmp_repo: Path):
        f = Demo("origin")
        assert f.forge_url == "https://demo.example.com"
        assert f.project_id == "demo/repo"


class TestUpload:
    def test_upload_is_a_noop(self, tmp_repo: Path):
        run_cmd("jj", "config", "set", "--repo", "pr.forge", "demo")
        (tmp_repo / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        # Should not raise, and should not touch the actual remote.
        run_cmd("jj", "pr", "upload")


class TestDownload:
    def test_download_is_a_noop(self, tmp_repo: Path):
        run_cmd("jj", "config", "set", "--repo", "pr.forge", "demo")
        # Should not raise, regardless of the identifier passed in.
        run_cmd("jj", "pr", "download", "123")


class TestRebase:
    def test_rebase_is_a_noop(self, tmp_repo: Path):
        run_cmd("jj", "config", "set", "--repo", "pr.forge", "demo")
        # Should not raise, regardless of the identifier passed in.
        run_cmd("jj", "pr", "rebase")


class TestList:
    def test_list_returns_demo_data(self, tmp_repo: Path):
        run_cmd("jj", "config", "set", "--repo", "pr.forge", "demo")
        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) > 0
        assert {item["cr_id"] for item in js} == {"#101", "#102", "#103", "#104"}
        # Demonstrates a range of states, checks, and blockers.
        states = {item["state"]["name"] for item in js}
        assert "Accepted" in states
        assert "Blocked" in states
        assert any(item["checks"] for item in js)
        assert any(item["blockers"] for item in js)


class TestLog:
    def test_log_annotates_every_commit(self, tmp_repo: Path):
        run_cmd("jj", "config", "set", "--repo", "pr.forge", "demo")
        (tmp_repo / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")

        log_output = run_cmd("jj", "pr", "log")
        assert "Test commit 1" in log_output

    def test_log_is_deterministic(self, tmp_repo: Path):
        run_cmd("jj", "config", "set", "--repo", "pr.forge", "demo")
        (tmp_repo / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")

        # Rich assigns a random per-render `id=NNNNNN` to each hyperlink escape
        # sequence, so strip those before comparing for content equality.
        def _strip_link_ids(s: str) -> str:
            return re.sub(r"id=\d+", "id=X", s)

        first = _strip_link_ids(run_cmd("jj", "pr", "log"))
        second = _strip_link_ids(run_cmd("jj", "pr", "log"))
        assert first == second
