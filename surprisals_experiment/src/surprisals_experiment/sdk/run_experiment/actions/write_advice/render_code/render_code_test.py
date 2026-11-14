"""Timeout feedback uses recorded attempts and preserves partial source files."""

import json

import pytest
from run_database import ExperimentDatabase
from surprisals_experiment.sdk.utils.write import write

from .render_code import render_code


@pytest.mark.parametrize('attempts', [1, 3])
@pytest.mark.parametrize('partial', [False, True])
async def test_exhausted_timeout_feedback(config, attempts, partial):
    turn_id = 'windows/0/forks/0/turns/0'
    write(config.output / 'windows/0/window.json', '{}')
    write(config.output / 'windows/0/forks/0/fork.json', '{}')
    write(config.output / turn_id / 'metadata.json', '{"advice": null}')
    for number in range(attempts):
        attempt = config.output / turn_id / 'ts/0/attempts' / str(number)
        write(attempt / 'generation.json', json.dumps({'timed_out': True}))
        if partial:
            write(attempt / 'src/partial.py', 'print(')
    config.t_sample_retries = 10
    feedback = await render_code(config, ExperimentDatabase(config.output), turn_id)
    source = '<file path="partial.py">\nprint(\n</file>\n' if partial else ''
    detail = 'partial code is shown above' if partial else 'no code was produced'
    assert feedback == (
        f'<code>\n<T-0>\n{source}'
        f'T timed out after {attempts} {"attempt" if attempts == 1 else "attempts"}; {detail}.\n'
        '</T-0>\n</code>'
    )


async def test_successful_retry_shows_only_completed_attempt(config):
    turn_id = 'windows/0/forks/0/turns/0'
    write(config.output / 'windows/0/window.json', '{}')
    write(config.output / 'windows/0/forks/0/fork.json', '{}')
    write(config.output / turn_id / 'metadata.json', '{"advice": null}')
    attempts = config.output / turn_id / 'ts/0/attempts'
    write(attempts / '0/generation.json', '{"timed_out": true}')
    write(attempts / '0/src/partial.py', 'print(')
    write(attempts / '1/generation.json', '{"exit_code": 0}')
    write(attempts / '1/src/main.py', 'print(2)')
    write(attempts / '1/tests.json', json.dumps({'cases': [
        {'index': i, 'stdout': '2', 'stderr': '', 'passed': True, 'status': 'passed'} for i in range(2)
    ]}))
    assert await render_code(config, ExperimentDatabase(config.output), turn_id) == (
        '<code>\n<T-0>\n<file path="main.py">\nprint(2)\n</file>\n'
        '<results>2/2 test cases passed</results>\n</T-0>\n</code>'
    )
