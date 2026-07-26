import hashlib

import httpx

from ...utils import cr, jj, text

# A handful of canned states/checks used to annotate `jj log`, cycled through
# deterministically based on each commit's change id.
_DEMO_LOG_STATES: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("Draft", "cyan", []),
    ("Needs Review", "yellow", [("lint", "green"), ("tests", "yellow")]),
    ("Accepted", "green", [("lint", "green"), ("tests", "green")]),
    ("Blocked", "red", [("lint", "green"), ("tests", "red")]),
]


def log_cmd(remote: str, args: list[str]) -> str:
    def _pr_ids_to_states(pr_ids: list[str]) -> dict[str, str]:
        return {pr_id: _demo_annotation(pr_id) for pr_id in pr_ids}

    return jj.log_with_annotations(
        args,
        "commit.change_id().normal_hex()",
        _pr_ids_to_states,
    )


def _demo_annotation(seed: str) -> str:
    name, color, checks = _DEMO_LOG_STATES[_stable_index(seed, len(_DEMO_LOG_STATES))]
    state = cr.State(name, color=color, url=httpx.URL("http://demo"))
    return text.rich_str(state, *[_check_to_str(name, color) for name, color in checks])


def _check_to_str(name: str, color: str) -> str:
    icon = {"green": "✔", "red": "✗", "yellow": "…"}.get(color, "?")
    return f"[link=http://demo][{color}]{icon}[/{color}][/link]"


def _stable_index(seed: str, n: int) -> int:
    """A deterministic (but not predictable at a glance) index in [0, n)."""
    digest = hashlib.sha256(seed.encode()).digest()
    return int.from_bytes(digest, "big") % n
