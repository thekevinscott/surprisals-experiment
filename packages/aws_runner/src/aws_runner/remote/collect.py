import subprocess

from aws_runner.config import ROOT
from aws_runner.remote.mirror import mirror
from aws_runner.remote.ssh import ssh


def collect(config, instance, directory):
    mirror(config, instance, directory)
    subprocess.run(
        ssh(config, instance) + [f"touch {ROOT}/collected; sync"], check=True
    )
