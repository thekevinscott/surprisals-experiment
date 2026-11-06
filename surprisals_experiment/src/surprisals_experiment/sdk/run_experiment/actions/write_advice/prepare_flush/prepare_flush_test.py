"""Build flush inputs using only persisted run artifacts."""

import json
from advice_artifacts import write_advice

import pytest

from surprisals_experiment.config import Config
from surprisals_experiment.sdk.database import ExperimentDatabase, QuestionDatabase
from surprisals_experiment.sdk.run_experiment.actions.write_advice.prepare_flush import prepare_flush

PASS = 'print(int(input()) * 2)\n'


@pytest.mark.parametrize('measure', ['characters', 'surprisal'])
async def test_selects_and_reads_best_from_run_folder_alone(config, measure):
    config = Config(**(config.model_dump() | {
        'cap_strategy': measure, 'scorer_base_url': 'http://scorer/v1', 't_samples': 2,
    }))
    config.fork_dir.mkdir(parents=True)
    (config.window_dir / 'window.json').write_text('{}')
    (config.fork_dir / 'fork.json').write_text('{}')
    problem = QuestionDatabase(config.problem_dir)
    database = ExperimentDatabase(config.output)
    assert await prepare_flush(config, problem, database) == await problem.question

    # Numeric ties favor 2 over 10; smaller failed/incomplete attempts cannot win.
    for number, measurement, results in [
        (10, 5, [True, True]), (2, 5, [True, True]), (1, 9, [True, True]),
        (3, 1, [True, False]), (4, 0, [True]),
    ]:
        directory = config.attempt_dir(number)
        directory.mkdir(parents=True)
        write_advice(config, directory, f'advice {number}', measurement,
                     [[f'advice {number}', measurement]] if measure == 'surprisal' else None)
        for sample, passed in enumerate(results):
            folder = config.t_dir(number, sample)
            (folder / 'attempts/0').mkdir(parents=True)
            (folder / 'attempts/0/generation.json').write_text('{"exit_code": 0}')
            (folder / 'attempts/0/tests.json').write_text(json.dumps({'cases': [{'index': 0, 'passed': passed, 'status': 's', 'stdout': '', 'stderr': ''}]}))
    for sample in range(2):
        src = config.t_dir(2, sample) / 'attempts/0/src'
        (src / 'nested').mkdir(parents=True)
        (src / 'main.py').write_text(f'print({sample})\n')
        (src / 'nested/helper.py').write_text(f'VALUE = {sample}\n')
    prompt = await prepare_flush(config, problem, database)
    assert prompt.count('<attempt>') == 1
    assert '<index>2</index>' in prompt
    assert '<advice>\nadvice 2\n</advice>' in prompt
    assert '<results>' not in prompt
    if measure == 'surprisal':
        assert '<bits>\nadvice 2<5.0>\n</bits>' in prompt
        assert '<length>' not in prompt
    else:
        assert '<length>5 characters</length>' in prompt
        assert '<bits>' not in prompt
    for sample in range(2):
        assert f'<T-{sample}>' in prompt
        assert f'print({sample})' in prompt
        assert f'VALUE = {sample}' in prompt
    # Files, not a retained Attempt instance, supply each call's text and code.
    write_advice(config, config.attempt_dir(2), 'updated advice', 5,
                 [['updated advice', 5]] if measure == 'surprisal' else None)
    (config.t_dir(2, 1) / 'attempts/0/src/main.py').write_text('print("updated")')
    updated = await prepare_flush(config, problem, database)
    assert '<advice>\nupdated advice\n</advice>' in updated
    assert 'print("updated")' in updated


async def test_ties_across_windows_and_forks_go_to_the_earliest_turn(config):
    config.output.mkdir()
    for turn in ['windows/10/forks/0/turns/1', 'windows/9/forks/2/turns/35', 'windows/9/forks/1/turns/35']:
        directory = config.output / turn
        (directory / 'ts/0/attempts/0').mkdir(parents=True)
        (directory.parents[3] / 'window.json').write_text('{}')
        (directory.parents[1] / 'fork.json').write_text('{}')
        write_advice(config, directory, turn, 5)
        (directory / 'ts/0/attempts/0/generation.json').write_text('{"exit_code": 0}')
        (directory / 'ts/0/attempts/0/tests.json').write_text(json.dumps({'cases': [{'index': 0, 'passed': True, 'status': 's', 'stdout': '', 'stderr': ''}]}))
    config = Config(**(config.model_dump() | {'t_samples': 1}))
    prompt = await prepare_flush(config, QuestionDatabase(config.problem_dir), ExperimentDatabase(config.output))
    assert '<advice>\nwindows/9/forks/1/turns/35\n</advice>' in prompt

async def test_keeps_best_attempt_even_above_old_size_budget(config):
    advice = config.attempt_dir(0)
    advice.mkdir(parents=True)
    (config.window_dir / 'window.json').write_text('{}')
    (config.fork_dir / 'fork.json').write_text('{}')
    write_advice(config, advice, 'double it', 9)
    sample = config.t_dir(0, 0)
    (sample / 'src').mkdir(parents=True)
    (sample / 'src/main.py').write_text(PASS)
    (sample / 'generation.json').write_text('{"exit_code": 0}')
    (sample / 'tests.json').write_text(json.dumps({'cases': [{'index': 0, 'passed': True, 'status': 's', 'stdout': '', 'stderr': ''}]}))
    prompt = await prepare_flush(config, QuestionDatabase(config.problem_dir), ExperimentDatabase(config.output))
    assert prompt.count('<attempt>') == 1
    assert '<advice>\ndouble it\n</advice>' in prompt
    assert PASS.rstrip() in prompt
