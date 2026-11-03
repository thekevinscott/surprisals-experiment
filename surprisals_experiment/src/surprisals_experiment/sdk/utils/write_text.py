"""Publish complete artifacts with a same-directory rename."""

import tempfile
from pathlib import Path


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, prefix=f'.{path.name}.', delete_on_close=False) as file:
        file.write(text)
        file.close()
        Path(file.name).replace(path)
