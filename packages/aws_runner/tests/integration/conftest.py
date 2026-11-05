import subprocess
from argparse import Namespace
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

from aws_runner.cloud.setup import setup


@pytest.fixture
def cloud(tmp_path):
    with mock_aws():
        ec2 = boto3.client(
            "ec2",
            region_name="us-east-1",
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )
        args = Namespace(
            config=tmp_path / "config.json",
            region="us-east-1",
            ami="ami-12345678",
            cidr="192.0.2.1/32",
            instance_type="t3.small",
            volume_size=20,
        )
        setup(ec2, args)
        import json

        yield ec2, args, json.loads(args.config.read_text())


@pytest.fixture
def transport():
    with (
        patch("subprocess.run") as execute,
        patch("subprocess.Popen") as stream,
        patch("time.sleep"),
    ):
        execute.return_value = subprocess.CompletedProcess([], 0, stdout="0\n")
        yield execute, stream
