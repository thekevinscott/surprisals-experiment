"""Publish complete artifacts with a same-directory rename."""

import tempfile
from pathlib import Path


def write(path: Path, content: str | bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('wb' if isinstance(content, bytes) else 'w', dir=path.parent, prefix=f'.{path.name}.', delete_on_close=False) as file:
        file.write(content)
        file.close()
        Path(file.name).replace(path)
