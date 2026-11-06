import subprocess

from aws_runner.config import ROOT
from aws_runner.remote.ssh import ssh


def watch(config, instance):
    script = f"""#!/bin/sh
while [ ! -f {ROOT}/exit-code ]; do sleep 1; done
for second in $(seq 1 120); do
    if [ -f {ROOT}/collected ]; then exit 0; fi
    sleep 1
done
/sbin/shutdown -h now
"""
    connection = ssh(config, instance)
    subprocess.run(
        connection + [f"cat > {ROOT}/watch.sh"], input=script, text=True, check=True
    )
    subprocess.run(
        connection
        + [
            f"sudo systemd-run --unit=aws-runner-collect /bin/sh {ROOT}/watch.sh"
            " || systemctl is-active -q aws-runner-collect"
        ],
        check=True,
    )
