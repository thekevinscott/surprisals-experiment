"""Build flush inputs using only persisted run artifacts."""

import json
from advice_artifacts import write_advice
from next_u_prompt import next_u_prompt

import pytest

from surprisals_experiment.config import Config


@pytest.mark.parametrize('measure', ['characters', 'surprisal'])
async def test_selects_and_reads_best_from_run_folder_alone(config, botbox_script, chat_provider, measure):
    config = Config(**(config.model_dump() | {
        'cap_strategy': measure, 'scorer_base_url': 'http://scorer/v1', 't_samples': 2,
    }))
    assert await next_u_prompt(config, botbox_script, chat_provider) == (config.problem_dir / 'question.txt').read_text()

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
            folder.mkdir(parents=True)
            (folder / 'generation.json').write_text('{"exit_code": 0}')
            (folder / 'tests.json').write_text(json.dumps({'cases': [{'index': 0, 'passed': passed, 'status': 's', 'stdout': '', 'stderr': ''}]}))
    for sample in range(2):
        src = config.t_dir(2, sample) / 'src'
        (src / 'nested').mkdir(parents=True)
        (src / 'main.py').write_text(f'print({sample})\n')
        (src / 'nested/helper.py').write_text(f'VALUE = {sample}\n')
    prompt = await next_u_prompt(config, botbox_script, chat_provider)
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
    (config.t_dir(2, 1) / 'src/main.py').write_text('print("updated")')
    updated = await next_u_prompt(config, botbox_script, chat_provider)
    assert '<advice>\nupdated advice\n</advice>' in updated
    assert 'print("updated")' in updated


async def test_ties_across_windows_and_forks_go_to_the_earliest_turn(config, botbox_script, chat_provider):
    config.output.mkdir()
    for turn in ['windows/10/forks/1/turns/1', 'windows/9/forks/2/turns/35', 'windows/9/forks/1/turns/35']:
        directory = config.output / turn
        (directory / 'ts/0').mkdir(parents=True)
        (directory.parents[3] / 'window.json').write_text('{}')
        (directory.parents[1] / 'fork.json').write_text('{}')
        write_advice(config, directory, turn, 5)
        (directory / 'ts/0/generation.json').write_text('{"exit_code": 0}')
        (directory / 'ts/0/tests.json').write_text(json.dumps({'cases': [{'index': 0, 'passed': True, 'status': 's', 'stdout': '', 'stderr': ''}]}))
    prompt = await next_u_prompt(config, botbox_script, chat_provider)
    assert '<advice>\nwindows/9/forks/1/turns/35\n</advice>' in prompt
