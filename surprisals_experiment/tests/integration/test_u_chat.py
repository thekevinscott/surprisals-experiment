"""Real chat streaming, feedback, and incident regressions at the HTTP boundary."""

import json

import pytest

from run_one_window import run_one_window

PASS = 'print(int(input()) * 2)\n'
USAGE = {'prompt_tokens': 100, 'completion_tokens': 30, 'total_tokens': 130,
         'prompt_tokens_details': {'cached_tokens': 50, 'cache_write_tokens': 10},
         'completion_tokens_details': {'reasoning_tokens': 20}, 'cost': 0.000123}


async def test_feeds_every_t_source_of_the_best_attempt_back(
    config, botbox_script, chat_provider, monkeypatch,
):
    from conftest import FakeSession

    config.t_samples = 2
    config.max_u_turns = 2
    botbox_script.advice.extend(['long advice', 'short'])
    mutating_code = ("from pathlib import Path\nn = input()\nPath('evaluation-only.txt').write_text(n)\n"
                     "Path('helper.py').write_text('MUTATED')\nprint(int(n) * 2)\n")
    botbox_script.solutions.extend([mutating_code, PASS, PASS, PASS])
    original = FakeSession.message

    async def write_helpers(session, text):
        result = await original(session, text)
        output = session.mounts['/solution']
        (output / 'helper.py').write_text('VALUE = 42\n')
        (output / 'nested').mkdir()
        (output / 'nested/extra.py').write_text('EXTRA = 7\n')
        (output / 'binary.dat').write_bytes(b'\xff')
        (output / 'hidden.json').symlink_to((config.problem_dir / 'input_output.json'))
        return result

    monkeypatch.setattr(FakeSession, 'message', write_helpers)
    assert await run_one_window(config, on_delta=None) == config.t_dir(1, 0) / 'src'
    assert len(botbox_script.sessions) == 4
    feedback = chat_provider[1]['messages'][-1]['content']
    assert '/solutions/' not in feedback
    assert '<length>11 characters</length>' in feedback
    assert feedback.count('<file path="helper.py">\nVALUE = 42\n</file>') == 1
    assert '<file path="helper.py">\nMUTATED\n</file>' in feedback
    assert feedback.count('<file path="nested/extra.py">\nEXTRA = 7\n</file>') == 2
    assert mutating_code.rstrip() in feedback
    assert '<file path="evaluation-only.txt">' in feedback
    assert PASS.rstrip() in feedback
    assert 'hidden.json' not in feedback
    assert 'binary.dat' not in feedback


async def test_sends_and_records_exact_roles(
    config, botbox_script, chat_provider,
):
    config.max_u_turns = 3
    chunked = lambda text: {'deltas': [{'role': 'assistant', 'content': c} for c in text]}
    botbox_script.advice.extend(map(chunked, ['tiny', 'long advice', 'longer advice']))
    botbox_script.solutions.extend([PASS] * 3)
    assert await run_one_window(config, on_delta=None) == config.t_dir(0, 0) / 'src'
    assert len(chat_provider) == 3
    for request in chat_provider:
        assert {m['role'] for m in request['messages']} <= {'system', 'user', 'assistant'}
    transcript = [json.loads(line) for line in (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]
    assert {m['role'] for m in transcript} <= {'system', 'user', 'assistant'}
    assert [m['content'] for m in transcript if m['role'] == 'assistant'] == ['tiny', 'long advice', 'longer advice']


async def test_records_an_exact_role_for_an_incomplete_reply(config, botbox_script, no_retry_wait):
    botbox_script.advice.extend([{
        'deltas': [{'role': 'assistant', 'content': 'par'}, {'role': 'assistant', 'content': 'tial'}],
        'finish': 'length', 'usage': USAGE,
    }] * 9)
    with pytest.raises(RuntimeError, match='U chat'):
        await run_one_window(config, on_delta=None)
    transcript = [json.loads(line) for line in (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]
    assert transcript[-1] == {'role': 'assistant', 'content': 'partial', '_complete': False}
    usage = [json.loads(line) for line in (config.u_transcripts / 'usage.jsonl').read_text().splitlines()]
    assert len(usage) == 9
    assert all(entry['usage'] == USAGE for entry in usage)


async def test_does_not_accept_empty_replies(config, botbox_script, no_retry_wait):
    botbox_script.advice.extend([{'deltas': [{'role': 'assistant'}], 'finish': None}] * 9)
    with pytest.raises(RuntimeError, match='U chat'):
        await run_one_window(config, on_delta=None)
    assert not botbox_script.sessions


async def test_preserves_the_prompt_on_provider_failure(config, botbox_script, no_retry_wait):
    botbox_script.advice.extend([{'status': 400}] * 9)
    with pytest.raises(RuntimeError, match='provider failed'):
        await run_one_window(config, on_delta=None)
    assert not botbox_script.sessions
    assert (config.problem_dir / 'question.txt').read_text() in (config.u_transcripts / 'messages.jsonl').read_text()
