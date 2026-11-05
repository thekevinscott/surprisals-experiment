import shlex
import subprocess
from threading import Thread

from aws_runner.config import ROOT
from aws_runner.remote.receive import receive
from aws_runner.remote.ssh import ssh


def follow(config, instance, offsets):
    script = f"""import json
import time
from pathlib import Path

root = Path({ROOT!r})
offsets = {offsets!r}
while True:
    done = (root / 'exit-code').exists()
    for index, name in enumerate(['command.stdout.log', 'command.stderr.log']):
        path = root / 'run' / name
        if path.exists():
            with path.open('rb') as source:
                source.seek(offsets[index])
                while chunk := source.read(65536):
                    print(json.dumps([index, chunk.hex()]), flush=True)
                offsets[index] = source.tell()
    if done:
        break
    time.sleep(0.2)
"""
    stream = subprocess.Popen(
        ssh(config, instance) + [f"exec python3 -u -c {shlex.quote(script)}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    reader = Thread(target=receive, args=(stream, offsets))
    reader.start()
    return stream, reader
