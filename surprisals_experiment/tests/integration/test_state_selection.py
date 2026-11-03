import json

import pytest

from surprisals_experiment.sdk.run_experiment.state.read_state import read_state


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) if isinstance(value, dict) else value)


async def test_state_tracks_published_artifacts(config):
    config.output.mkdir()
    assert await read_state(config) == 'not_started'
    write(config.attempt_dir(0) / 'error.txt', 'interrupted')
    assert await read_state(config) == 'advice_missing'
    write(config.advice_dir(0, 0) / 'advice.txt', 'Double.')
    assert await read_state(config) == 'unscored'
    write(config.advice_dir(0, 0) / 'metadata.json', {'measurement': 7})
    assert await read_state(config) == 'solutions_missing'
    write(config.t_dir(0, 0) / 'run.json', {'exit_code': 0})
    assert await read_state(config) == 'untested'
    write(config.t_dir(0, 0) / 'tests.json', {'all_passed': True})
    assert await read_state(config) == 'feedback_missing'
    write(config.attempt_dir(0) / 'feedback.txt', 'Continue.')
    assert await read_state(config) == 'result_missing'
    write(config.result_file, {'attempts': 1})
    assert await read_state(config) == 'exhausted'
    config.max_u_turns = 2
    assert await read_state(config) == 'next_attempt'


async def test_all_samples_must_finish_generation_and_tests(config):
    config.t_samples = 2
    config.t_sample_retries = 1
    write(config.advice_dir(0, 0) / 'advice.txt', 'Double.')
    write(config.advice_dir(0, 0) / 'metadata.json', {'measurement': 7})
    write(config.t_dir(0, 0) / 'run.json', {'exit_code': 0})
    write(config.t_dir(0, 0) / 'tests.json', {'all_passed': True})
    write(config.t_dir(0, 1) / 'run.json', {'exit_code': -1})
    write(config.t_dir(0, 1) / 'timeouts.txt', 'timeout\n')
    assert await read_state(config) == 'solutions_missing'
    write(config.t_dir(0, 1) / 'timeouts.txt', 'timeout\ntimeout\n')
    assert await read_state(config) == 'untested'
    write(config.t_dir(0, 1) / 'tests.json', {'all_passed': False})
    assert await read_state(config) == 'feedback_missing'


@pytest.mark.parametrize('passed,expected', [(True, 'next_attempt'), (False, 'exhausted')])
async def test_stopping_uses_completed_attempts(config, passed, expected):
    config.max_u_turns = None
    config.max_turns_without_improvement = 1
    write(config.advice_dir(0, 0) / 'advice.txt', 'Double.')
    write(config.advice_dir(0, 0) / 'metadata.json', {'measurement': 7})
    write(config.t_dir(0, 0) / 'tests.json', {'all_passed': passed})
    write(config.attempt_dir(0) / 'feedback.txt', 'Continue.')
    assert await read_state(config) == 'result_missing'
    write(config.result_file, {'attempts': 1})
    assert await read_state(config) == expected
