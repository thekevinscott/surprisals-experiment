"""Fixtures and assertions for the shared advice artifacts."""

import json
from hashlib import sha256


def advice_directory(config, text):
    return config.output / "advices" / sha256(text.encode("utf-8")).hexdigest()


def read_score(config, attempt):
    metadata = json.loads((config.attempt_dir(attempt) / "metadata.json").read_text())
    return json.loads((config.output / "advices" / metadata["advice"] / "advice.json").read_text())


def write_advice(config, turn, text, score, tokens=None):
    directory = advice_directory(config, text)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "advice.txt").write_bytes(text.encode("utf-8"))
    (directory / "advice.json").write_text(json.dumps({
        "score": score, **({"tokens": tokens} if tokens is not None else {}),
    }))
    (turn / "metadata.json").write_text(json.dumps({"advice": directory.name}))
