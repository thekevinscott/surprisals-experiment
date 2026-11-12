import subprocess
import sys
from unittest.mock import patch

from aws_runner.cli import main


def test_run_missing_config(tmp_path):
    config = tmp_path / "missing.json"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from aws_runner.cli import main; raise SystemExit(main())",
            "--config",
            str(config),
            "run",
            str(tmp_path / "run"),
            "--",
            "true",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert str(config) in result.stderr
    assert "aws_runner setup --ami <ami> --region <region>" in result.stderr
    assert "Traceback" not in result.stderr
    assert len(result.stderr.splitlines()) == 1


def test_setup_defaults_to_m7i_large(monkeypatch):
    monkeypatch.setattr(
        "sys.argv", ["aws_runner", "setup", "--region", "us-east-1", "--ami", "ami-1"]
    )
    with patch("aws_runner.cli.setup") as setup, patch("aws_runner.cli.boto3"):
        main()
    assert setup.call_args.args[1].instance_type == "m7i.large"


def test_run_requires_a_command_before_loading_config(monkeypatch):
    import pytest

    monkeypatch.setattr("sys.argv", ["aws_runner", "run", "some-run", "--"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
