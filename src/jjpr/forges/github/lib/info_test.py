from pathlib import Path

import pytest

pytestmark = pytest.mark.github

from ....conftest import run_cmd
from .info import get_forge_info


class TestInfo:
    def test_info(self, tmp_home: Path, tmp_repo: Path, api_token: str):
        r = "git@github.com:shish/jj-pr.git"
        run_cmd("git", "remote", "set-url", "origin", r)
        f = get_forge_info("origin")
        assert f.remote_url == "ssh://git@github.com/shish/jj-pr.git"
        assert f.forge_url == "https://github.com"
        assert f.project_id == "shish/jj-pr"
