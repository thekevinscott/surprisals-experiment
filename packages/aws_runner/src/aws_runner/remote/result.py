import subprocess

from aws_runner.config import ROOT
from aws_runner.remote.ssh import ssh


def result(config, instance):
    status = subprocess.run(
        ssh(config, instance)
        + [f"if [ -f {ROOT}/exit-code ]; then cat {ROOT}/exit-code; fi"],
        check=True,
        capture_output=True,
        text=True,
    )
    return int(status.stdout.strip()) if status.stdout.strip() else None
