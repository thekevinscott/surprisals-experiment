import sys
from datetime import UTC, datetime


def timestamp(step):
    print(
        f"{datetime.now(UTC).isoformat(timespec='seconds')} {step}",
        file=sys.stderr,
        flush=True,
    )
