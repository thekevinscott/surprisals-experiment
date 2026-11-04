"""Read the summary preceding cases in our tests.json format without loading outputs."""

import json
from pathlib import Path


def read_summary(path: Path) -> dict:
    header = ""
    with path.open() as results:
        for line in results:
            if line.startswith('  "cases":'):
                break
            header += line
    return json.loads(header.rstrip().removesuffix(",") + "}")
