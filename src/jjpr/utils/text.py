import re
import typing as t
from io import StringIO

from rich.console import Console


def rich_str(*obj: t.Any) -> str:
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=True, color_system="truecolor")
    console.print(*obj, end="")
    return buffer.getvalue()


def remove_ansi(line: str) -> str:
    ansi_escape = re.compile(
        r"\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)"  # OSC sequences (e.g. hyperlinks)
        r"|(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]"  # CSI and other two-byte sequences
    )
    return ansi_escape.sub("", line)
