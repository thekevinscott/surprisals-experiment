import subprocess

from aws_runner.config import ROOT
from aws_runner.remote.ssh import ssh
from aws_runner.remote.watch import watch


def execute(config, instance):
    watch(config, instance)
    subprocess.run(
        ssh(config, instance)
        + [
            f"sudo systemd-run --unit=aws-runner --property=User=ubuntu "
            f"--property=StandardOutput=journal --property=StandardError=journal /bin/sh {ROOT}/command.sh"
        ],
        check=True,
    )
