"""Publish complete artifacts with a same-directory rename."""

import os
import tempfile
from pathlib import Path


def write(path: Path, content: str | bytes):
    if path.exists() and path.read_bytes() == (content.encode() if isinstance(content, str) else content):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('wb' if isinstance(content, bytes) else 'w', dir=path.parent, prefix=f'.{path.name}.', delete_on_close=False) as file:
        file.write(content)
        file.flush()
        os.fsync(file.fileno())
        file.close()
        Path(file.name).replace(path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
