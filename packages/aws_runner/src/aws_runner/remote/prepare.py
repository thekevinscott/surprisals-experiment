import subprocess

from aws_runner.config import ROOT
from aws_runner.remote.connect import connect


def prepare(config, instance):
    connection = connect(config, instance)
    script = f"""set -eu
sudo cloud-init status --wait
sudo apt-get update -qq
sudo apt-get install -y -qq rsync curl ca-certificates build-essential
# dirsql is pinned to a git rev (#443), so uv compiles it.
curl -fsSL https://sh.rustup.rs | sh -s -- -y -q --profile minimal
sudo ln -sf "$HOME"/.cargo/bin/* /usr/local/bin/
sudo mkdir -p {ROOT}
sudo chown ubuntu:ubuntu {ROOT}
mkdir -p {ROOT}/run
"""
    subprocess.run(connection + ["sh -s"], input=script, text=True, check=True)
