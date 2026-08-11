from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.demo]

from .download import download_cmd


class TestDownload:
    def test_download_is_a_noop(self, clone: Path):
        download_cmd("origin", "123")
