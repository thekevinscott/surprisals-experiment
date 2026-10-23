"""Include all text source files from every T's pre-test snapshot."""

import json
from pathlib import Path

from surprisals_experiment.prompts import render


def read_implementations(snapshot: Path) -> str:
    implementations = {}
    for sample in sorted(path for path in snapshot.iterdir() if path.is_dir()):
        sources = {}
        for path in sorted(sample.rglob("*")):
            if not path.is_file() or not path.resolve().is_relative_to(sample.resolve()):
                continue
            try:
                sources[str(path.relative_to(sample))] = path.read_text()
            except UnicodeDecodeError:
                continue
        implementations[render("t_label.j2", sample_name=sample.name)] = sources
    return json.dumps(implementations, ensure_ascii=False, indent=2)
