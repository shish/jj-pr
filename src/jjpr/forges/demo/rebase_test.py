from pathlib import Path

from .rebase import rebase_cmd


class TestRebase:
    def test_rebase_is_a_noop(self, clone: Path):
        rebase_cmd("origin", [])
