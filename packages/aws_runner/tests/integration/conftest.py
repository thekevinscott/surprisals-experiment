from argparse import Namespace
from functools import partial
from unittest.mock import DEFAULT, patch

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
            ami="ami-12345678",
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


@pytest.fixture
def capacity_shortage(cloud):
    from botocore.exceptions import ClientError

    ec2, _, _ = cloud
    original = ec2.run_instances
    with (
        patch.object(
            ec2,
            "run_instances",
            wraps=original,
            side_effect=[
                ClientError(
                    {
                        "Error": {
                            "Code": "InsufficientInstanceCapacity",
                            "Message": "full",
                        }
                    },
                    "RunInstances",
                ),
                DEFAULT,
            ],
        ) as allocate,
        patch("time.sleep") as sleep,
    ):
        yield allocate, sleep
