import json
from pathlib import Path

from ...conftest import run_cmd


class TestList:
    def test_list_empty(self, clone: Path):
        text = run_cmd("jj", "pr", "list")
        assert text == "No items found."
        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert js == []

    def test_list_one(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        run_cmd("jj", "pr", "upload")

        text = run_cmd("jj", "pr", "list")
        assert text
        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 1
        assert js[0]["title"]["text"] == "Test commit 1"
        assert js[0]["cr_id"].startswith("c")

    def test_list_multiple(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")

        (clone / "test_file2.txt").write_text("Test content 2")
        run_cmd("jj", "commit", "-m", "Test commit 2")

        run_cmd("jj", "pr", "upload")

        text = run_cmd("jj", "pr", "list")
        assert text
        js = json.loads(run_cmd("jj", "pr", "--format", "json", "list"))
        assert len(js) == 2
        titles = {item["title"]["text"] for item in js}
        assert "Test commit 1" in titles
        assert "Test commit 2" in titles
