"""Run the experiment through the Python SDK."""

import json
import traceback

from collections.abc import Callable
from functools import partial
from inspect import isawaitable
from pathlib import Path

from state_machine import Stop, state_machine

from surprisals_experiment.config import Config
from ..utils.write_text import write_text
from ..utils.u_chat import open_u_session
from .actions.write_advice import write_advice
from .actions.score_advice import score_advice
from .actions.write_solutions import write_solutions
from .actions.run_tests import run_tests
from .actions.write_feedback import write_feedback
from .actions.write_result import write_result
from .state.artifacts import query
from .state.facts import run_facts
from .state.read_state import read_state
from .state.inputs import action_inputs


async def run_experiment(
    config: Config, *, on_delta: Callable[[str, str], None] | None,
    on_t_delta: Callable[[str, str], None] | None = None,
) -> Path | None:
    """Generate, test, and shorten advice until the no-improvement limit, turn limit, or interruption."""
    config.question_file.read_text()
    test_suite = json.loads(config.test_suite_file.read_text())
    if not isinstance(test_suite, dict) or test_suite.get("fn_name"):
        raise ValueError("Only stdin/stdout test suites are supported")
    inputs, outputs = test_suite.get("inputs"), test_suite.get("outputs")
    if (not isinstance(inputs, list) or not isinstance(outputs, list)
            or not inputs or len(inputs) != len(outputs)
            or not all(isinstance(value, str) for value in inputs + outputs)):
        raise ValueError("Test suite requires equally sized, nonempty inputs and outputs lists of strings")
    config.save_settings()
    async with open_u_session(config) as session:
        async def dispatch(name, action, **extra):
            arguments = await action_inputs(config, session, name)
            result = action(config, **arguments, **extra)
            if isawaitable(result):
                await result

        advice = partial(dispatch, 'write_advice', write_advice, on_delta=on_delta)
        actions = dict(
            not_started=advice, next_attempt=advice, advice_missing=advice,
            unscored=partial(dispatch, 'score_advice', score_advice, on_delta=on_delta),
            solutions_missing=partial(dispatch, 'write_solutions', write_solutions, on_delta=on_t_delta),
            untested=partial(dispatch, 'run_tests', run_tests, test_suite=test_suite),
            feedback_missing=partial(dispatch, 'write_feedback', write_feedback),
            result_missing=partial(dispatch, 'write_result', write_result), exhausted=Stop,
        )
        try:
            await state_machine(state=partial(read_state, config), actions=actions)
        except Exception:
            rows = await query(config, 'SELECT max(attempt) AS attempt FROM artifacts')
            if rows[0]['attempt'] is not None:
                write_text(config.attempt_dir(rows[0]['attempt']) / 'error.txt', traceback.format_exc())
            raise
    facts = (await query(config, run_facts(config)))[0]
    solution = config.t_dir(facts['best'], 0) / 'src' if facts['best'] is not None else None
    if solution is None:
        write_text(config.error_file, f"No passing solution after {facts['completed']} U turns\n")
    elif config.error_file.exists():
        config.error_file.unlink()
    return solution
