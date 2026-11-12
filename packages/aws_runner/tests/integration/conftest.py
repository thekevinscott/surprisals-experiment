from argparse import Namespace
from functools import partial
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws
from respond import respond

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
            ami=ec2.register_image(
                Name="test-root",
                RootDeviceName="/dev/sda1",
                BlockDeviceMappings=[
                    {"DeviceName": "/dev/sda1", "Ebs": {"VolumeSize": 8}}
                ],
            )["ImageId"],
            cidr="192.0.2.1/32",
            instance_type="t3.small",
            volume_size=20,
        )
        setup(ec2, args)
        import json

        yield ec2, args, json.loads(args.config.read_text())


@pytest.fixture
def transport(tmp_path):
    with (
        patch("subprocess.run") as execute,
        patch("subprocess.Popen") as stream,
        patch("time.sleep"),
    ):
        stream.return_value.poll.return_value = None
        stream.return_value.wait.return_value = 0
        state = {
            "checkout": str(tmp_path / "checkout"),
            "polls": ["0"],
            "fail_copy": False,
        }
        execute.side_effect = partial(respond, state)
        yield execute, stream, state


@pytest.fixture
def ticking_clock():
    with patch("time.monotonic", side_effect=[0, 5, 10, 10]) as clock:
        yield clock
