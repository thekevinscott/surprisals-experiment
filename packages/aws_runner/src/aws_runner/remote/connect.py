import subprocess
import time

from aws_runner.remote.ssh import ssh


def connect(config, instance):
    connection = ssh(config, instance)
    for attempt in range(120):
        if subprocess.run(connection + ["true"], capture_output=True).returncode == 0:
            return connection
        time.sleep(5)
    raise TimeoutError("Instance did not become reachable over SSH")
