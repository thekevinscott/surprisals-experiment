import subprocess

from aws_runner.config import ROOT
from aws_runner.remote.ssh import ssh


def result(config, instance):
    status = subprocess.run(
        ssh(config, instance)
        + [
            f"systemctl is-active aws-runner || true; "
            f"if [ -f {ROOT}/exit-code ]; then cat {ROOT}/exit-code; "
            f"[ -s {ROOT}/exit-code ] || echo 1; fi"
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    unit, _, code = status.stdout.partition("\n")
    running = unit.strip() not in ("inactive", "failed")
    return (int(code) if code.strip() else None), running
