"""Build U request inputs from the run's advice, feedback, and summary files."""

import json

from .compact import preamble
from .open_u_session import system_message


def measured_state(config, stop):
    best_advice = best_length = None
    stale = 0
    for attempt in range(stop):
        measurement = json.loads((config.advice_dir(attempt, 0) / "metadata.json").read_text())["measurement"]
        passed = all(json.loads((config.t_dir(attempt, sample) / "tests.json").read_text())["all_passed"]
                     for sample in range(config.t_samples))
        if passed and (best_length is None or measurement < best_length):
            best_length = measurement
            best_advice = (config.advice_dir(attempt, 0) / "advice.txt").read_text()
            stale = 0
        else:
            stale += 1
    return dict(best_advice=best_advice, best_length=best_length, turns_without_improvement=stale)


def build_messages(config, attempt):
    messages = [system_message(config)]
    question = config.question_file.read_text()
    if config.u_flush:
        current = question if attempt == 0 else (config.attempt_dir(attempt - 1) / "feedback.txt").read_text()
        return [*messages, {"role": "user", "content": current}]
    boundary = next((index for index in range(attempt, -1, -1)
                     if (config.attempt_dir(index) / "summary.txt").exists()), None)
    if boundary is None:
        messages.append({"role": "user", "content": question})
        start = 0
    else:
        summary = (config.attempt_dir(boundary) / "summary.txt").read_text()
        # Main keeps the measured state from this boundary in its preamble.
        messages.append({"role": "user", "content": preamble(
            question, summary, **measured_state(config, boundary),
        )})
        messages.append({"role": "user", "content":
                         (config.attempt_dir(boundary - 1) / "feedback.txt").read_text()})
        start = boundary
    for index in range(start, attempt):
        messages.append(json.loads((config.advice_dir(index, 0) / "reply.json").read_text()))
        messages.append({"role": "user", "content": (config.attempt_dir(index) / "feedback.txt").read_text()})
    return messages
