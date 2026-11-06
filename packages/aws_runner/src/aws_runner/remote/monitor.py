import subprocess
import sys
import time

from aws_runner.remote.execute import execute
from aws_runner.remote.follow import follow
from aws_runner.remote.mirror import mirror
from aws_runner.remote.result import result


def monitor(config, instance, directory):
    result_failing = False
    mirror_failing = False
    offsets = [0, 0]
    stream, reader = follow(config, instance, offsets)
    next_mirror = time.monotonic() + 10
    try:
        while True:
            if stream.poll() not in (None, 0):
                reader.join()
                stream, reader = follow(config, instance, offsets)
            try:
                code, running = result(config, instance)
                if code is None and not running:
                    execute(config, instance)
            except subprocess.CalledProcessError as error:
                if error.returncode != 255:
                    raise
                if not result_failing:
                    print(
                        "Exit-code check SSH failed; retrying",
                        file=sys.stderr,
                        flush=True,
                    )
                result_failing = True
                code = None
            else:
                if result_failing:
                    print("Exit-code check SSH recovered", file=sys.stderr, flush=True)
                result_failing = False
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
                    if not mirror_failing:
                        print(
                            "Live mirror SSH failed; retrying",
                            file=sys.stderr,
                            flush=True,
                        )
                    mirror_failing = True
                else:
                    if mirror_failing:
                        print("Live mirror SSH recovered", file=sys.stderr, flush=True)
                    mirror_failing = False
                    next_mirror = time.monotonic() + 10
            time.sleep(1)
    except BaseException:
        stream.terminate()
        stream.wait()
        reader.join()
        raise
