"""Flush shows the original question and only the earliest shortest all-pass attempt."""

import json
from importlib.resources import files

import pytest

from surprisals_experiment.config import Config
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.run_experiment.prepare_flush import Attempt, prepare_flush

PASS = 'print(int(input()) * 2)\n'
OTHER_PASS = 'n = int(input())\nprint(n + n)\n'
FAIL = 'print(0)\n'


@pytest.mark.parametrize('advices,passed,best', [
    (['failed first', 'failed second'], [False, False], None),
    (['failed first', 'successful advice', 'failed later'], [False, True, False], 1),
    (['long successful advice', 'short'], [True, True], 1),
    (['first', 'other'], [True, True], 0),
    (['best', 'later failure'], [True, False], 0),
], ids=['no-pass', 'one-pass-among-failures', 'shorter-pass', 'equal-pass', 'failure-after-best'])
async def test_shows_only_best_all_pass_attempt(config, botbox_script, chat_provider, advices, passed, best):
    config.u_flush = True
    config.t_samples = 2
    config.max_u_turns = len(advices) + 1
    config.question_file.write_text(config.question_file.read_text() + '\n')
    question = config.question_file.read_text()
    botbox_script.advice.extend([*advices, 'final'])
    for all_passed in [*passed, True]:
        botbox_script.solutions.extend([PASS, OTHER_PASS if all_passed else FAIL])
    await run_experiment(config, on_delta=None)
    messages = chat_provider[-1]['messages']
    assert len(messages) == 2
    assert messages[1]['role'] == 'user'
    prompt = messages[1]['content']
    if best is None:
        assert prompt == question
    else:
        code = '\n'.join(
            f'<T-{index}>\n<file path="main.py">\n{source.rstrip()}\n</file>\n</T-{index}>'
            for index, source in enumerate([PASS, OTHER_PASS])
        )
        assert prompt == (
            f'<original_question>\n{question.rstrip()}\n</original_question>\n\n'
            f'<attempt>\n<index>{best}</index>\n<length>{len(advices[best])} characters</length>\n'
            f'<advice>\n{advices[best]}\n</advice>\n'
            f'<code>\n{code}\n</code>\n</attempt>'
        )
    assert (config.attempt_dir(len(advices) - 1) / 'feedback.txt').read_text() == prompt
    assert chat_provider[0]['messages'][1]['content'] == question
    context = files('surprisals_experiment').joinpath('prompts/u/flush/context.txt').read_text()
    assert context in messages[0]['content']
    assert json.loads((config.output / 'settings.json').read_text())['u_flush'] is True


async def test_accumulates_chat_when_flush_is_disabled(
    config, botbox_script, chat_provider,
):
    config.max_u_turns = 3
    botbox_script.advice.extend(['double it', 'double', 'ok'])
    botbox_script.solutions.extend([PASS] * 3)
    await run_experiment(config, on_delta=None)
    context = files('surprisals_experiment').joinpath('prompts/u/chat/context.txt').read_text()
    assert context in chat_provider[0]['messages'][0]['content']
    assert [len(request['messages']) for request in chat_provider] == [2, 4, 6]
    for turn in [1, 2]:
        assert chat_provider[turn]['messages'][-1]['content'] == (config.attempt_dir(turn - 1) / 'feedback.txt').read_text()


def test_keeps_best_attempt_even_above_old_size_budget(config):
    config.u_compact_chars = 1
    history = [Attempt(0, 'double it', 9, ['passed 2 of 2 tests'], True, {'0': {'main.py': PASS}})]
    prompt = prepare_flush(config, history)
    assert prompt.count('<attempt>') == 1
    assert '<advice>\ndouble it\n</advice>' in prompt
    assert PASS.rstrip() in prompt


async def test_selects_by_bits_and_shows_only_best_token_scores(config, botbox_script, chat_provider, scorer_provider):
    scores = [[('Use', 1.123), (' a', 0.4), (' two', 0.3), ('-pointer', 0.2)], [('Sweep', 7.9), ('.', 0.06)],
              [('done', 1.0)]]
    scorer_provider.replies.extend(scores)
    config = Config(**(config.model_dump() | {
        'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1',
        'u_flush': True, 'max_u_turns': 3, 'max_turns_without_improvement': 3,
    }))
    botbox_script.advice.extend(['Use a two-pointer', 'Sweep.', 'done'])
    botbox_script.solutions.extend([PASS] * 3)
    await run_experiment(config, on_delta=None)
    prompt = chat_provider[2]['messages'][1]['content']
    assert prompt.count('<attempt>') == 1
    assert '<index>0</index>' in prompt
    assert '<length>' not in prompt
    assert '<results>' not in prompt
    assert '<bits>\nUse<1.1> a<0.4> two<0.3>-pointer<0.2>\n</bits>' in prompt
    assert 'Sweep' not in prompt


@pytest.mark.parametrize('measure', ['characters', 'surprisal'])
async def test_shows_only_the_selected_measure_and_no_results(
    config, botbox_script, chat_provider, scorer_provider, measure,
):
    config = Config(**(config.model_dump() | {
        'cap_strategy': measure, 'scorer_base_url': 'http://scorer/v1',
        'u_flush': True, 'max_u_turns': 2, 't_samples': 2,
    }))
    scorer_provider.replies.extend([[('double', 2.5)], [('next', 1.0)]])
    botbox_script.advice.extend(['double', 'next'])
    botbox_script.solutions.extend([PASS, OTHER_PASS] * 2)
    await run_experiment(config, on_delta=None)
    prompt = chat_provider[1]['messages'][1]['content']
    if measure == 'characters':
        assert '<length>6 characters</length>' in prompt
        assert '<bits>' not in prompt
    else:
        assert '<bits>\ndouble<2.5>\n</bits>' in prompt
        assert '<length>' not in prompt
    assert '<results>' not in prompt
    assert 'passed 2 of 2 tests' not in prompt
    assert '<advice>\ndouble\n</advice>' in prompt
    assert PASS.rstrip() in prompt
    assert OTHER_PASS.rstrip() in prompt
