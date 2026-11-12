import argparse
import json
from pathlib import Path

import boto3

from aws_runner.cloud.setup import setup
from aws_runner.config import CONFIG
from aws_runner.run import run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    commands = parser.add_subparsers(dest="action", required=True)
    init = commands.add_parser("setup")
    init.add_argument(
        "--ami", required=True, help="Pinned stock Ubuntu AMI in this region"
    )
    init.add_argument("--region", required=True)
    init.add_argument("--cidr", help="Caller IPv4 /32; otherwise detect public IP")
    init.add_argument("--instance-type", default="m7i.large")
    init.add_argument("--volume-size", type=int, default=20)
    job = commands.add_parser("run")
    job.add_argument("directory", type=Path)
    job.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == "setup":
        setup(boto3.client("ec2", region_name=args.region), args)
        return 0
    command = args.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("run requires -- <cmd>")
    try:
        config = json.loads(args.config.read_text())
    except FileNotFoundError:
        parser.exit(
            1,
            f"Missing config: {args.config}; "
            "run aws_runner setup --ami <ami> --region <region> first.\n",
        )
    return run(
        boto3.client("ec2", region_name=config["region"]),
        config,
        args.directory.resolve(),
        command,
    )
