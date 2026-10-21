"""Save agent transcript files outside the solution workspace."""

from collections.abc import Mapping
from pathlib import Path


def save_transcripts(transcripts: Mapping[str, str], directory: Path) -> None:
    """Preserve botbox transcript filenames relative to the agent home."""
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in transcripts.items():
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
