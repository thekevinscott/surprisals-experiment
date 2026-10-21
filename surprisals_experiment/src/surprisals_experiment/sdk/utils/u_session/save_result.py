"""Retain U's transcripts and process diagnostics after closing Pi."""

import json
from dataclasses import asdict

from botbox import RunResult

from surprisals_experiment.config import Config

from ..transcripts import save_transcripts


def save_result(result: RunResult, config: Config) -> None:
    diagnostics = asdict(result)
    save_transcripts(diagnostics.pop("transcript"), config.u_transcripts)
    config.u_run_file.write_text(json.dumps(diagnostics, indent=2) + "\n")
