import subprocess

import pytest

from jjpr import utils


class TestRun:
    def test_run_basic_command(self):
        output = utils.run(["echo", "hello"])
        assert output == "hello"

    def test_run_with_output(self):
        output = utils.run(["echo", "test output"])
        assert "test output" in output

    def test_run_skipping_output(self):
        output = utils.run(["echo", "test output"], cap=False)
        assert output is None

    def test_run_command_failure_raises_error(self):
        with pytest.raises(subprocess.CalledProcessError):
            utils.run(["false"])

    def test_run_strips_whitespace(self):
        output = utils.run(["echo", "  spaced  "])
        assert output == "spaced"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
