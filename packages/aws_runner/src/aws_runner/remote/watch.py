import shlex
import subprocess

from aws_runner.config import ROOT
from aws_runner.remote.ssh import ssh


def watch(config, instance):
    script = f"while [ ! -f {ROOT}/exit-code ]; do sleep 1; done; sleep 120; /sbin/shutdown -h now"
    subprocess.run(
        ssh(config, instance)
        + [
            f"sudo systemd-run --unit=aws-runner-orphan --collect /bin/sh -c {shlex.quote(script)}"
        ],
        check=True,
    )
