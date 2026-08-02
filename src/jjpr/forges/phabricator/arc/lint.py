import json
import logging
import shutil
import typing as t
from enum import StrEnum
from pathlib import Path

from ....utils import exec

log = logging.getLogger(__name__)


class LintStatus(StrEnum):
    NONE = "none"
    OKAY = "okay"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


LintResults = dict[str, list[t.Any]]


def lint_current_diff(pre_commit: bool) -> tuple[LintStatus, LintResults]:
    if not pre_commit:
        return (LintStatus.SKIP, {})
    if not Path(".arclint").exists():
        return (LintStatus.NONE, {})
    if not shutil.which("arc"):
        log.warning("arc not found in PATH, skipping lint")
        return (LintStatus.SKIP, {})
    try:
        lint_data = exec.run(
            "arc", "lint", "--apply-patches", "--output", "json", cap=True
        )
        lints_per_file = json.loads(lint_data)
        worst = LintStatus.OKAY
        for lints in lints_per_file.values():
            for lint in lints:
                if lint["severity"] == "warning":
                    worst = LintStatus.WARN
                if lint["severity"] == "error":
                    worst = LintStatus.FAIL
                    break
        return (worst, lints_per_file)
    except Exception:
        return (LintStatus.FAIL, {})
