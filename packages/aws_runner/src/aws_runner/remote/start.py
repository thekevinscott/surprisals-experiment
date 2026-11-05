import shlex
import subprocess

from aws_runner.config import ROOT
from aws_runner.remote.ssh import ssh


def start(config, instance, command, working_directory):
    script = f"""#!/bin/sh
export PATH=/home/ubuntu/.local/bin:$PATH
(
cd {shlex.quote(working_directory)} || exit 125
{shlex.join(command)}
)
code=$?
printf '%s\\n' "$code" > {ROOT}/exit-code.tmp
mv {ROOT}/exit-code.tmp {ROOT}/exit-code
sync
exit "$code"
"""
    connection = ssh(config, instance)
    subprocess.run(
        connection + [f"cat > {ROOT}/command.sh"], input=script, text=True, check=True
    )
    subprocess.run(
        connection
        + [
            f"sudo systemd-run --unit=aws-runner --property=User=ubuntu "
            f"--property=StandardOutput=journal --property=StandardError=journal /bin/sh {ROOT}/command.sh"
        ],
        check=True,
    )
