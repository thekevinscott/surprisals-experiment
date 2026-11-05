import subprocess
import time

from aws_runner.remote.follow import follow
from aws_runner.remote.mirror import mirror
from aws_runner.remote.result import result

SSH_FAILURE_TIMEOUT = 300


def monitor(config, instance, directory):
    result_failed_since = None
    mirror_failed_since = None
    offsets = [0, 0]
    stream, reader = follow(config, instance, offsets)
    next_mirror = time.monotonic() + 10
    try:
        while True:
            if stream.poll() not in (None, 0):
                reader.join()
                stream, reader = follow(config, instance, offsets)
            try:
                code = result(config, instance)
            except subprocess.CalledProcessError as error:
                if error.returncode != 255:
                    raise
                now = time.monotonic()
                if result_failed_since is None:
                    result_failed_since = now
                if now - result_failed_since >= SSH_FAILURE_TIMEOUT:
                    raise
                code = None
            else:
                result_failed_since = None
            if code is not None:
                status = stream.wait()
                reader.join()
                if status == 0:
                    return code
                time.sleep(1)
                stream, reader = follow(config, instance, offsets)
                continue
            if time.monotonic() >= next_mirror:
                try:
                    mirror(config, instance, directory)
                except subprocess.CalledProcessError as error:
                    if error.returncode != 255:
                        raise
                    now = time.monotonic()
                    if mirror_failed_since is None:
                        mirror_failed_since = now
                    if now - mirror_failed_since >= SSH_FAILURE_TIMEOUT:
                        raise
                else:
                    mirror_failed_since = None
                next_mirror = time.monotonic() + 10
            time.sleep(1)
    except BaseException:
        stream.terminate()
        stream.wait()
        reader.join()
        raise
