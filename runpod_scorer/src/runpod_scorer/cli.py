"""RunPod scorer lifecycle commands."""

import argparse
from pathlib import Path

from . import setup, teardown


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    up = commands.add_parser("up", help="Create a scorer and wait for readiness")
    up.add_argument("directory", type=Path)
    up.add_argument("--model", default=setup.DEFAULT_MODEL)
    up.add_argument("--gpu", default=setup.DEFAULT_GPU)
    down = commands.add_parser("down", help="Delete a scorer and confirm it is gone")
    down.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    if args.command == "up":
        setup.up(args.directory, args.model, args.gpu)
    else:
        teardown.down(args.directory)
