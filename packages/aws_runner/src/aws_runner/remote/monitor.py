import subprocess
import time

from aws_runner.config import ROOT
from aws_runner.remote.ssh import ssh


def monitor(config, instance, directory):
    connection = ssh(config, instance)
    stream = subprocess.Popen(
        connection + ["sudo journalctl -u aws-runner --lines=all -f -o cat --no-pager"]
    )
    try:
        while True:
            result = subprocess.run(
                connection
                + [f"if [ -f {ROOT}/exit-code ]; then cat {ROOT}/exit-code; fi"],
                check=True,
                capture_output=True,
                text=True,
            )
            if result.stdout.strip():
                time.sleep(1)
                return int(result.stdout.strip())
            time.sleep(1)
    finally:
        stream.terminate()
        stream.wait()
