import shlex
import subprocess

from aws_runner.config import ROOT
from aws_runner.remote.ssh import ssh


def mirror(config, instance, directory, timeout=None):
    directory.mkdir(parents=True, exist_ok=True)
    connection = ssh(config, instance)
    copy = subprocess.run(
        [
            "rsync",
            "-az",
            "--exclude=/stdout.log",
            "--exclude=/stderr.log",
            "--exclude=/run.json",
            "--exclude=/run.lock",
            "--exclude=/memory.jsonl",
            "--exclude=/stdout-*.txt",
            "--exclude=/stderr-*.txt",
            "-e",
            shlex.join(connection[:-1]),
            f"{connection[-1]}:{ROOT}/run/",
            str(directory) + "/",
        ],
        timeout=timeout,
    )
    if copy.returncode not in (0, 24):
        raise subprocess.CalledProcessError(copy.returncode, copy.args)
