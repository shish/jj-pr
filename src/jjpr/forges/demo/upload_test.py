from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.demo]

from ...conftest import run_cmd
from .upload import upload_cmd


class TestUpload:
    def test_upload_is_a_noop(self, clone: Path):
        (clone / "test_file.txt").write_text("Test content")
        run_cmd("jj", "commit", "-m", "Test commit 1")
        # Should not raise, and should not touch the actual remote.
        upload_cmd("origin", "@")
