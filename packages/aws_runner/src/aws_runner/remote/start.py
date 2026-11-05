import shlex
import subprocess

from aws_runner.config import ROOT
from aws_runner.remote.ssh import ssh


def start(config, instance, command):
    script = f"""#!/bin/sh
cd {ROOT}/run || exit 125
{shlex.join(command)}
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
