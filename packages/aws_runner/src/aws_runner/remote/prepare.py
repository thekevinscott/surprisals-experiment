import shlex
import subprocess

from aws_runner.config import ROOT
from aws_runner.remote.connect import connect


def prepare(config, instance, volume):
    connection = connect(config, instance)
    serial = shlex.quote(volume.replace("-", ""))
    script = f"""set -eu
sudo cloud-init status --wait
sudo apt-get update -qq
sudo apt-get install -y -qq rsync curl ca-certificates
DEVICE=/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_{serial}
while [ ! -b "$DEVICE" ] && [ ! -b /dev/xvdf ]; do sleep 1; done
if [ ! -b "$DEVICE" ]; then DEVICE=/dev/xvdf; fi
if ! sudo blkid "$DEVICE"; then sudo mkfs.ext4 -F "$DEVICE"; fi
sudo mkdir -p {ROOT}
UUID=$(sudo blkid -s UUID -o value "$DEVICE")
printf 'UUID=%s {ROOT} ext4 defaults,nofail 0 2\\n' "$UUID" | sudo tee -a /etc/fstab
sudo mount {ROOT}
sudo chown ubuntu:ubuntu {ROOT}
mkdir -p {ROOT}/run
"""
    subprocess.run(connection + ["sh -s"], input=script, text=True, check=True)
