"""Fresh and accumulated history, selective eviction, and token feedback."""

import json
from importlib.resources import files

from surprisals_experiment.config import Config
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.run_experiment.prepare_flush import Attempt, prepare_flush, render

PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'


async def test_sends_every_previous_advice_with_its_results(config, botbox_script, chat_provider):
    config.u_flush = True
    config.t_samples = 2
    config.max_u_turns = 6
    advices = ['double "input" {exact}', 'x', 'a much longer successful advice', 'y', 'double', 'z']
    sources = [[PASS, PASS], [PASS, FAIL], [PASS, PASS], [FAIL, FAIL], [PASS, PASS], [FAIL, FAIL]]
    botbox_script.advice.extend(advices)
    botbox_script.solutions.extend(source for batch in sources for source in batch)
    await run_experiment(config, on_delta=None)
    assert len(chat_provider) == 6
    resources = files('surprisals_experiment').joinpath('prompts')
    system = chat_provider[0]['messages'][0]
    assert resources.joinpath('u/flush/context.txt').read_text() in system['content']
    assert resources.joinpath('u/chat/context.txt').read_text() not in system['content']
    assert chat_provider[0]['messages'][1]['content'] == config.question_file.read_text()
    question = config.question_file.read_text().rstrip('\n')

    def expected(i, code):
        results = '\n'.join(f'T-{t}: passed {2 if s == PASS else 0} of 2 tests' for t, s in enumerate(sources[i]))
        block = (f'<attempt>\n<index>{i}</index>\n<length>{len(advices[i])} characters</length>\n'
                 f'<advice>\n{advices[i]}\n</advice>\n<results>\n{results}\n</results>\n')
        if code:
            block += '<code>\n' + '\n'.join(
                f'<T-{t}>\n<file path="main.py">\n{s.rstrip()}\n</file>\n</T-{t}>' for t, s in enumerate(sources[i])
            ) + '\n</code>\n'
        return block + '</attempt>'

    latest_pass = {1: 0, 2: 0, 3: 2, 4: 2, 5: 4}
    for turn, request in enumerate(chat_provider[1:], 1):
        messages = request['messages']
        assert len(messages) == 2
        assert messages[0] == system
        assert messages[1]['role'] == 'user'
        prompt = messages[1]['content']
        assert prompt == f'<original_question>\n{question}\n</original_question>\n\n' + '\n'.join(
            expected(i, i in (turn - 1, latest_pass[turn])) for i in range(turn)
        )
        assert (config.attempt_dir(turn - 1) / 'feedback.txt').read_text() == prompt
    settings = json.loads((config.output / 'settings.json').read_text())
    assert settings['u_flush'] is True
    transcript = [json.loads(line) for line in (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]
    assert [m['content'] for m in transcript if m['role'] == 'assistant'] == advices


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


def test_ejects_oldest_failures_then_oldest_successes_to_fit_the_budget(config):
    kept = [2, 4]
    history = [Attempt(i, chr(97 + i) * 50, 50, ['passed 1 of 1 tests'], not i % 2, {}) for i in range(5)]
    config.u_compact_chars = len(render(config, [history[i] for i in kept]))
    assert prepare_flush(config, history) == render(config, [history[i] for i in kept])


async def test_shows_per_token_bits_for_each_previous_advice(config, botbox_script, chat_provider, scorer_provider):
    scores = [[('Use', 2.123), (' a', 0.4), (' two', 3.0), ('-pointer', 5.2)], [('Sweep', 7.9), ('.', 0.06)],
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
    assert 'Use<2.1> a<0.4> two<3.0>-pointer<5.2>' in prompt
    assert 'Sweep<7.9>.<0.1>' in prompt
