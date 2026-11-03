"""Include all text source files from every T's pre-test snapshot."""

import json
from pathlib import Path


def read_source(sample: Path) -> dict[str, str]:
    sources = {}
    for path in sorted(sample.rglob("*")):
        if not path.is_file() or not path.resolve().is_relative_to(sample.resolve()):
            continue
        try:
            sources[str(path.relative_to(sample))] = path.read_text()
        except UnicodeDecodeError:
            continue
    return sources


def read_sources(snapshot: Path) -> dict[str, dict[str, str]]:
    return {sample.name: read_source(sample)
            for sample in sorted(path for path in snapshot.iterdir() if path.is_dir())}


def read_implementations(snapshot: Path) -> str:
    return json.dumps(
        {f"T {name}": sources for name, sources in read_sources(snapshot).items()}, ensure_ascii=False, indent=2,
    )
