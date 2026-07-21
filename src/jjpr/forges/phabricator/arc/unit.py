import json
import logging
import shutil
from enum import StrEnum
from pathlib import Path

from ....utils import exec

log = logging.getLogger(__name__)


class UnitStatus(StrEnum):
    NONE = "none"
    OKAY = "okay"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


def unit_current_diff(pre_commit: bool) -> tuple[UnitStatus, list]:
    if not pre_commit:
        return (UnitStatus.SKIP, [])
    if not Path(".arcunit").exists():
        return (UnitStatus.NONE, [])
    if not shutil.which("arc"):
        log.warning("arc not found in PATH, skipping unit")
        return (UnitStatus.SKIP, [])
    try:
        fail_data = exec.run("arc", "unit", "--output", "json", cap=True)
        fails = json.loads(fail_data)
        worst = UnitStatus.OKAY
        for _file, fails in fails.items():
            for lint in fails:
                if lint["severity"] == "warning":
                    worst = UnitStatus.WARN
                if lint["severity"] == "error":
                    worst = UnitStatus.FAIL
                    break
        return (worst, fails)
    except Exception:
        return (UnitStatus.FAIL, [])
