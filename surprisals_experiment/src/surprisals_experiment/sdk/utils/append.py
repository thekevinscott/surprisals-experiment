"""Add content to the end of a file in place and sync it."""

import os
from pathlib import Path


def append(path: Path, content: str | bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    created = not path.exists()
    with path.open('ab' if isinstance(content, bytes) else 'a') as file:
        file.write(content)
        file.flush()
        os.fsync(file.fileno())
    if created:
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
