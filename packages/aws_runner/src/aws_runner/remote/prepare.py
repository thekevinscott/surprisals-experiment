import shlex
import subprocess
import time

from aws_runner.config import ROOT
from aws_runner.remote.ssh import ssh


def prepare(config, instance, volume):
    connection = ssh(config, instance)
    for attempt in range(120):
        if subprocess.run(connection + ["true"], capture_output=True).returncode == 0:
            break
        time.sleep(5)
    else:
        raise TimeoutError("Instance did not become reachable over SSH")
    serial = shlex.quote(volume.replace("-", ""))
    script = f"""set -eu
sudo cloud-init status --wait
sudo apt-get update -qq
sudo apt-get install -y -qq rsync
DEVICE=/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_{serial}
if [ ! -e "$DEVICE" ]; then DEVICE=/dev/xvdf; fi
while [ ! -b "$DEVICE" ]; do sleep 1; done
if ! sudo blkid "$DEVICE"; then sudo mkfs.ext4 -F "$DEVICE"; fi
sudo mkdir -p {ROOT}
sudo mount "$DEVICE" {ROOT}
sudo chown ubuntu:ubuntu {ROOT}
mkdir -p {ROOT}/run
"""
    subprocess.run(connection + ["sh -s"], input=script, text=True, check=True)
