from pathlib import Path

from ._info import get_forge_info


class TestInfo:
    def test_info(self, clone: Path):
        f = get_forge_info("origin")
        assert f.forge_url == "https://demo.example.com"
        assert f.project_id == "demo/repo"
