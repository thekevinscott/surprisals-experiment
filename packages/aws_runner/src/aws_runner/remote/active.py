import subprocess

from aws_runner.remote.ssh import ssh


def active(config, instance):
    status = subprocess.run(
        ssh(config, instance) + ["systemctl is-active aws-runner || true"],
        check=True,
        capture_output=True,
        text=True,
    )
    return status.stdout.strip() == "active"
