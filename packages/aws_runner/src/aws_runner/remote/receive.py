import json
import sys


def receive(stream, offsets):
    with stream.stdout:
        for line in stream.stdout:
            if not line.endswith(b"\n"):
                break
            index, encoded = json.loads(line)
            chunk = bytes.fromhex(encoded)
            output = (sys.stdout.buffer, sys.stderr.buffer)[index]
            output.write(chunk)
            output.flush()
            offsets[index] += len(chunk)
