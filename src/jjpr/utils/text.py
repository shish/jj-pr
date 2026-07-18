import re
from io import StringIO

from rich.console import Console


def rich_str(*obj) -> str:
    buffer = StringIO()
    console = Console(file=buffer, force_terminal=True, color_system="truecolor")
    console.print(*obj, end="")
    return buffer.getvalue()


def remove_ansi(line):
    ansi_escape = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")
    return ansi_escape.sub("", line)
