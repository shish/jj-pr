import logging
from pathlib import Path

import httpx
import pytest

from .. import exc
from ..conftest import run_cmd
from . import detect

log = logging.getLogger(__name__)


class TestDetectForgeFromUrl:
    def test_detect_github(self):
        result = detect.detect_forge_from_url(
            httpx.URL("https://github.com/user/repo.git")
        )
        assert result == "github"

    def test_detect_github_with_www(self):
        result = detect.detect_forge_from_url(
            httpx.URL("https://www.github.com/user/repo.git")
        )
        assert result == "github"

    def test_detect_phabricator(self):
        result = detect.detect_forge_from_url(
            httpx.URL("https://phabricator.example.com/repo/name")
        )
        assert result == "phabricator"

    def test_detect_gerrit(self):
        result = detect.detect_forge_from_url(
            httpx.URL("https://gerrit.example.com/repo")
        )
        assert result == "gerrit"

    def test_detect_unknown_forge(self):
        result = detect.detect_forge_from_url(
            httpx.URL("https://unknown.example.com/repo")
        )
        assert result is None

    def test_detect_forge_case_insensitive(self):
        result = detect.detect_forge_from_url(httpx.URL("https://GITHUB.COM/user/repo"))
        assert result == "github"


class TestGetForge:
    def test_get_forge_explicit(self, tmp_repo: Path):
        run_cmd("git", "remote", "add", "secret", "https://secret.com/user/blag.git")
        forge = detect.get_forge("github", "secret")
        assert forge is not None
        assert forge.__class__.__name__ == "GitHub"

    def test_get_forge_auto_detect_github(self, tmp_repo: Path):
        run_cmd("git", "remote", "add", "gh", "https://github.com/user/repo.git")
        forge = detect.get_forge(None, "gh")
        assert forge is not None
        assert forge.__class__.__name__ == "GitHub"

    def test_get_forge_nonexistent_remote(self, tmp_repo: Path):
        with pytest.raises(exc.UserError):
            detect.get_forge(None, "nonexistent")

    def test_get_forge_no_auto_detect_no_forge_specified(self, tmp_repo: Path):
        """Test that unknown URL without explicit forge returns None."""
        run_cmd(
            "git", "remote", "add", "unrecognised", "https://unknown.example.com/repo"
        )
        with pytest.raises(exc.UserError):
            detect.get_forge(None, "unrecognised")
