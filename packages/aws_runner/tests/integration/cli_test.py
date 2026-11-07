from unittest.mock import patch

from aws_runner.cli import main


def test_setup_defaults_to_m7i_large(monkeypatch):
    monkeypatch.setattr(
        "sys.argv", ["aws_runner", "setup", "--region", "us-east-1", "--ami", "ami-1"]
    )
    with patch("aws_runner.cli.setup") as setup, patch("aws_runner.cli.boto3"):
        main()
    assert setup.call_args.args[1].instance_type == "m7i.large"
