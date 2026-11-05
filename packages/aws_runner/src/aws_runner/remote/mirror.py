import shlex
import subprocess

from aws_runner.config import ROOT
from aws_runner.remote.ssh import ssh


def mirror(config, instance, directory):
    directory.mkdir(parents=True, exist_ok=True)
    connection = ssh(config, instance)
    subprocess.run(
        [
            "rsync",
            "-az",
            "--exclude=/stdout.log",
            "--exclude=/stderr.log",
            "-e",
            shlex.join(connection[:-1]),
            f"{connection[-1]}:{ROOT}/run/",
            str(directory) + "/",
        ],
        check=True,
    )
