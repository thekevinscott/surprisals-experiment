"""RunPod scorer lifecycle commands."""

import argparse

from . import setup, teardown


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    up = commands.add_parser("up", help="Join the shared scorer and wait for readiness")
    up.add_argument("--model", default=setup.DEFAULT_MODEL)
    up.add_argument("--gpu", default=setup.DEFAULT_GPU)
    up.add_argument("--experiment", default="experiments/surprisal", help="Experiment folder for pod cost records")
    commands.add_parser(
        "down", help="Release this invocation; delete the last user's scorer"
    )
    commands.add_parser("reap", help="Remove dead users and delete unused scorers")
    args = parser.parse_args(argv)
    if args.command == "up":
        setup.up(args.model, args.gpu, args.experiment)
    elif args.command == "down":
        teardown.down()
    else:
        teardown.reap()
