import subprocess

from aws_runner.config import ROOT
from aws_runner.remote.ssh import ssh


def shipped(config, instance):
    status = subprocess.run(ssh(config, instance) + [f"test -f {ROOT}/command.sh"])
    if status.returncode not in (0, 1):
        raise subprocess.CalledProcessError(status.returncode, status.args)
    return status.returncode == 0
