import shlex
import subprocess

from aws_runner.config import ROOT
from aws_runner.remote.ssh import ssh


def follow(config, instance):
    script = f"""import sys
import time
from pathlib import Path

root = Path({ROOT!r})
offsets = [0, 0]
while True:
    done = (root / 'exit-code').exists()
    for index, (name, output) in enumerate([
        ('command.stdout.log', sys.stdout.buffer),
        ('command.stderr.log', sys.stderr.buffer),
    ]):
        path = root / 'run' / name
        if path.exists():
            with path.open('rb') as source:
                source.seek(offsets[index])
                while chunk := source.read(65536):
                    output.write(chunk)
                    output.flush()
                offsets[index] = source.tell()
    if done:
        break
    time.sleep(0.2)
"""
    return subprocess.Popen(
        ssh(config, instance) + [f"python3 -u -c {shlex.quote(script)}"]
    )
