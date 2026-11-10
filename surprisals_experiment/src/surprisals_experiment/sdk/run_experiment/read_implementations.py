"""Include text source files from the supplied solution directories."""

from pathlib import Path

MAX_FILE_BYTES = 64 * 1024


def read_sources(solutions: dict[int, Path]) -> dict[str, dict[str, str | int]]:
    implementations = {}
    for index, sample in solutions.items():
        sources = {}
        for path in sorted(sample.rglob("*")):
            if not path.is_file() or not path.resolve().is_relative_to(sample.resolve()):
                continue
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                sources[str(path.relative_to(sample))] = size
                continue
            try:
                sources[str(path.relative_to(sample))] = path.read_text()
            except UnicodeDecodeError:
                continue
        implementations[str(index)] = sources
    return implementations
