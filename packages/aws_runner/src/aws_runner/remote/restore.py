import subprocess

from aws_runner.config import ROOT
from aws_runner.remote.ssh import ssh


def restore(config, instance):
    subprocess.run(ssh(config, instance) + [f"sh {ROOT}/layout.sh"], check=True)
