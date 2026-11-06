"""Fixtures and assertions for the shared advice artifacts."""

import json
from hashlib import sha256


def advice_directory(config, text):
    return config.output / "advices" / sha256(text.encode("utf-8")).hexdigest()


def read_score(config, attempt):
    metadata = json.loads((config.attempt_dir(attempt) / "metadata.json").read_text())
    return json.loads((config.output / metadata["advice"] / "advice.json").read_text())
