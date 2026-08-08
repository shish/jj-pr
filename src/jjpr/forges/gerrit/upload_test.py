import json
from pathlib import Path

from ...conftest import run_cmd
from ...utils import jj


class TestUpload:
    def test_push_one_head(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "upload")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 1
        assert js[0]["title"]["text"] == "Test commit 1"

    def test_push_one_cwd(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "upload")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 1
        assert js[0]["title"]["text"] == "Test commit 1"

    def test_push_one_then_two(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "upload")

        (clone / "test_file2.txt").write_text("Test content 2")
        run_cmd("jj", "commit", "-m", "Test commit 2")
        run_cmd("jj", "pr", "upload")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 2
        assert js[0]["title"]["text"] == "Test commit 2"
        assert js[1]["title"]["text"] == "Test commit 1"

    def test_push_two_at_once(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")

        (clone / "test_file2.txt").write_text("Test content 2")
        run_cmd("jj", "commit", "-m", "Test commit 2")

        run_cmd("jj", "pr", "upload")

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 2
        assert js[0]["title"]["text"] == "Test commit 2"
        assert js[1]["title"]["text"] == "Test commit 1"

    def push_other_branch(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "upload")
        change_id = jj.change_id("@")

        jj.new("@-")
        (clone / "test_file2.txt").write_text("Test content 2")
        run_cmd("jj", "commit", "-m", "Test commit 2")
        run_cmd("jj", "pr", "upload", change_id)

        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 2
        assert js[1]["title"]["text"] == "Test commit 1"
