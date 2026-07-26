import json
from pathlib import Path

from ...conftest import run_cmd
from ._info import get_forge_info


class TestInfo:
    def test_info(self, tmp_home: Path, tmp_repo: Path):
        r = "https://phab.mycorp.com/source/my-repo.git"
        run_cmd("git", "remote", "set-url", "origin", r)
        arcrc = {
            "hosts": {
                "https://phab.mycorp.com/api/": {
                    "token": "api-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                }
            }
        }
        (tmp_home / ".arcrc").write_text(json.dumps(arcrc))
        arcconfig = {
            "phabricator.uri": "https://phab.mycorp.com",
            "repository.callsign": "TESTREPO",
            "arc.land.onto.default": "main",
        }
        (tmp_repo / ".arcconfig").write_text(json.dumps(arcconfig))
        f = get_forge_info("origin")
        assert f.remote_url == r
        assert f.forge_url == "https://phab.mycorp.com"
        assert f.project_id == "TESTREPO"
        assert f.default_merge_target == "main"
