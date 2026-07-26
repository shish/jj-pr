import typing as t
from pathlib import Path

import pytest

from ...conftest import run_cmd


@pytest.fixture
def clone(tmp_repo: Path) -> t.Generator[Path, None, None]:
    run_cmd("jj", "config", "set", "--repo", "pr.forge", "demo")
    yield tmp_repo
