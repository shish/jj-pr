from unittest import mock

import httpx

from ..utils import git
from . import base


class TestForgeInfo:
    def test_init(self) -> None:
        with mock.patch.object(
            git,
            "get_remote_url",
            return_value=httpx.URL("https://example.com/dummy.git"),
        ):
            f = base.ForgeInfo("origin")

        assert f.remote == "origin"
        assert f.remote_url == "https://example.com/dummy.git"
        assert f.forge_url == "https://example.com/dummy.git"
        assert f.project_id == "unknown"
        assert f.default_merge_target is None
        assert f.client is None
