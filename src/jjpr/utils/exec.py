import logging
import shlex
import subprocess
import typing as t

log = logging.getLogger(__name__)


@t.overload
def run(*args: str, cap: t.Literal[True]) -> str: ...


@t.overload
def run(*args: str, cap: t.Literal[False]) -> None: ...


@t.overload
def run(*args: str) -> str: ...


def run(*args: str, cap: bool = True) -> str | None:
    cmd = list(args)

    # run jjpr commands directly without invoking subprocess
    # (should only be used in unit tests, not in production code)
    if len(cmd) >= 2 and cmd[0] == "jj" and cmd[1] == "pr":
        return _run_jjpr_cmd(cmd[2:])

    try:
        if not cap:
            log.debug(f"run({shlex.join(cmd)}) -> ...")
        result = subprocess.run(
            cmd,
            capture_output=cap,
            text=True,
            check=True,
        )
        if cap:
            rs = result.stdout.strip()
            if "\n" in rs:
                log.debug(f"run({shlex.join(cmd)}) -> \n{rs}")
            else:
                log.debug(f"run({shlex.join(cmd)}) -> {rs!r}")
            return rs
        else:
            return None
    except subprocess.CalledProcessError as e:
        log.info(f"run({shlex.join(cmd)}) failed")
        log.debug(f"Return code: {e.returncode}")
        if cap:
            log.debug(f"stdout: {e.stdout.strip()}")
            log.debug(f"stderr: {e.stderr.strip()}")
        raise


def _run_jjpr_cmd(args: list[str]) -> str:
    from typer.testing import CliRunner

    from .. import main

    runner = CliRunner()
    result = runner.invoke(main.app, args)
    if result.exit_code != 0:
        raise subprocess.CalledProcessError(
            returncode=result.exit_code,
            cmd=["jj", "pr"] + list(args),
            output=result.output,
        )
    return result.output.strip()
