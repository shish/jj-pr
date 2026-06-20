import json
from pathlib import Path

from jjpr.main import main

from ...conftest import run_cmd


class TestGithubPush:
    def test_import(self):
        # otherwise pytest complains that nothing touched jjpr
        assert main is not None

    def test_clone(self, clone: Path):
        remote_url = run_cmd("git", "config", "--get", "remote.origin.url").strip()
        assert remote_url.startswith("https://github.com/")

    def test_pr_push_one_head(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "push")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 1
        assert js[0]["title"] == "Test commit 1"

    def test_pr_push_one_cwd(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "push")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 1
        assert js[0]["title"] == "Test commit 1"

    def test_pr_push_one_then_two(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "push")

        (clone / "test_file2.txt").write_text("Test content 2")
        run_cmd("jj", "commit", "-m", "Test commit 2")
        run_cmd("jj", "pr", "push")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 1
        assert js[0]["title"] == "Test commit 1"

    def test_pr_push_two_at_once(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")

        (clone / "test_file2.txt").write_text("Test content 2")
        run_cmd("jj", "commit", "-m", "Test commit 2")

        run_cmd("jj", "pr", "push")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 1
        assert js[0]["title"] == "Test commit 2"
