from unittest import TestCase, mock

import httpx

from ..utils import git
from . import base


_REMOTE_URL = httpx.URL("https://example.com/dummy.git")


class TestForgeInfo(TestCase):
    def test_init(self) -> None:
        with mock.patch.object(git, "get_remote_url", return_value=_REMOTE_URL):
            f = base.ForgeInfo("origin")

        assert f.remote == "origin"
        assert f.remote_url == "https://example.com/dummy.git"
        assert f.forge_url == "https://example.com/dummy.git"
        assert f.project_id == "unknown"
        assert f.default_merge_target is None

    def test_without_client(self) -> None:
        with mock.patch.object(git, "get_remote_url", return_value=_REMOTE_URL):
            f = base.ForgeInfo[None]("origin")

        assert f._client is None
        with self.assertRaises(ValueError):
            _ = f.client

    def test_with_client(self) -> None:
        with mock.patch.object(git, "get_remote_url", return_value=_REMOTE_URL):
            f = base.ForgeInfo[str]("origin")
            f.client = "dummy_client"

        assert f.client == "dummy_client"
