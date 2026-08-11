from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.demo]

from .rebase import rebase_cmd


class TestRebase:
    def test_rebase_is_a_noop(self, clone: Path):
        rebase_cmd("origin", [])
