import time

from aws_runner.remote.follow import follow
from aws_runner.remote.mirror import mirror
from aws_runner.remote.result import result


def monitor(config, instance, directory):
    offsets = [0, 0]
    stream, reader = follow(config, instance, offsets)
    next_mirror = time.monotonic() + 10
    try:
        while True:
            if stream.poll() not in (None, 0):
                reader.join()
                stream, reader = follow(config, instance, offsets)
            code = result(config, instance)
            if code is not None:
                status = stream.wait()
                reader.join()
                if status == 0:
                    return code
                time.sleep(1)
                stream, reader = follow(config, instance, offsets)
                continue
            if time.monotonic() >= next_mirror:
                mirror(config, instance, directory)
                next_mirror = time.monotonic() + 10
            time.sleep(1)
    except BaseException:
        stream.terminate()
        stream.wait()
        reader.join()
        raise
