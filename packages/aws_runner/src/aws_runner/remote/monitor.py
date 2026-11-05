import subprocess
import time

from aws_runner.remote.follow import follow
from aws_runner.remote.mirror import mirror
from aws_runner.remote.result import result


def monitor(config, instance, directory):
    stream = follow(config, instance)
    next_mirror = time.monotonic() + 10
    try:
        while True:
            if stream.poll() not in (None, 0):
                raise subprocess.CalledProcessError(stream.returncode, stream.args)
            code = result(config, instance)
            if code is not None:
                status = stream.wait()
                if status:
                    raise subprocess.CalledProcessError(status, stream.args)
                return code
            if time.monotonic() >= next_mirror:
                mirror(config, instance, directory)
                next_mirror = time.monotonic() + 10
            time.sleep(1)
    except BaseException:
        stream.terminate()
        stream.wait()
        raise
