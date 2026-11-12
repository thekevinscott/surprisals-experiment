import shlex
import subprocess

from aws_runner.config import ROOT
from aws_runner.remote.ssh import ssh
from aws_runner.remote.watch import watch


def start(config, instance, command, working_directory):
    connection = ssh(config, instance)
    script = f"""#!/bin/sh
export PATH=/home/ubuntu/.local/bin:$PATH
(
cd {shlex.quote(working_directory)} || exit 125
{shlex.join(command)}
) >> {ROOT}/run/aws/command.stdout.log 2>> {ROOT}/run/aws/command.stderr.log
code=$?
printf '%s\\n' "$code" > {ROOT}/exit-code.tmp
mv {ROOT}/exit-code.tmp {ROOT}/exit-code
sync
exit "$code"
"""
    watch(config, instance)
    subprocess.run(
        connection
        + [
            "sudo systemd-run --unit=aws-runner --collect --expand-environment=no "
            "--property=User=ubuntu "
            "--property=StandardOutput=journal --property=StandardError=journal "
            f"/bin/sh -c {shlex.quote(script)}"
        ],
        check=True,
    )
