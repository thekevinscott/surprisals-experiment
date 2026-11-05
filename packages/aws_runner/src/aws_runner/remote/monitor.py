import subprocess
import time

from aws_runner.remote.mirror import mirror
from aws_runner.remote.result import result
from aws_runner.remote.ssh import ssh


def monitor(config, instance, directory):
    connection = ssh(config, instance)
    stream = subprocess.Popen(
        connection + ["sudo journalctl -u aws-runner --lines=all -f -o cat --no-pager"]
    )
    next_mirror = time.monotonic() + 10
    try:
        while True:
            code = result(config, instance)
            if code is not None:
                time.sleep(1)
                return code
            if time.monotonic() >= next_mirror:
                mirror(config, instance, directory)
                next_mirror = time.monotonic() + 10
            time.sleep(1)
    finally:
        stream.terminate()
        stream.wait()
