from pathlib import Path

from ...conftest import run_cmd
from ...utils import netrc
from ._info import get_forge_info


class TestInfo:
    def test_info(self, tmp_home: Path, tmp_repo: Path):
        r = "ssh://git@gerrit.mycorp.com:29418/example/repo.git"
        run_cmd("git", "remote", "set-url", "origin", r)
        run_cmd("jj", "config", "set", "--repo", "gerrit.default-remote-branch", "main")
        netrc.write("gerrit.mycorp.com", "testuser", "testtoken")
        f = get_forge_info("origin")
        assert f.remote_url == r
        assert f.forge_url == "https://gerrit.mycorp.com"
        assert f.project_id == "example/repo"
        assert f.default_merge_target == "main"
