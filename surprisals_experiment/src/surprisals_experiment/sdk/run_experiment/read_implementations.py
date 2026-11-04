"""Include text source files from the supplied solution directories."""

import json
from pathlib import Path


def read_sources(solutions: list[Path]) -> dict[str, dict[str, str]]:
    implementations = {}
    for index, sample in enumerate(solutions):
        sources = {}
        for path in sorted(sample.rglob("*")):
            if not path.is_file() or not path.resolve().is_relative_to(sample.resolve()):
                continue
            try:
                sources[str(path.relative_to(sample))] = path.read_text()
            except UnicodeDecodeError:
                continue
        implementations[str(index)] = sources
    return implementations


def read_implementations(solutions: list[Path]) -> str:
    return json.dumps(
        {f"T {name}": sources for name, sources in read_sources(solutions).items()}, ensure_ascii=False, indent=2,
    )
