"""Compaction preserves measured state and accounts for reasoning once."""

import json
from datetime import datetime

import pytest

from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.utils.u_chat import open_u_session

PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'
USAGE = {'prompt_tokens': 100, 'completion_tokens': 30, 'total_tokens': 130,
         'prompt_tokens_details': {'cached_tokens': 50, 'cache_write_tokens': 10},
         'completion_tokens_details': {'reasoning_tokens': 20}, 'cost': 0.000123}


async def test_keeps_measured_best_and_streak_across_repeated_compactions(
    config, botbox_script, chat_provider,
):
    config.u_compact_chars = 1
    config.max_u_turns = 4
    # First success; then shorter but failing; then a new best; then no improvement.
    best = 'double\n"input" {exact}'
    botbox_script.advice.extend([
        best, 'Failures: none. Best length is 999 (incorrect summary).', 'x',
        'Do not print zero.', 'double', 'Remember integer parsing.', 'longer advice',
    ])
    botbox_script.advice = type(botbox_script.advice)(
        {'deltas': [{'role': 'assistant', 'content': text}], 'usage': USAGE}
        for text in botbox_script.advice
    )
    botbox_script.solutions.extend([PASS, FAIL, PASS, PASS])
    assert await run_experiment(config, on_delta=None) == config.t_dir(2, 0) / 'src'
    assert len(chat_provider) == 7
    system = chat_provider[0]['messages'][0]
    for request_index, attempt, advice, length, streak in [
        (2, 0, best, len(best), 0), (4, 1, best, len(best), 1), (6, 2, 'double', 6, 0),
    ]:
        messages = chat_provider[request_index]['messages']
        assert len(messages) == 3
        assert messages[0] == system
        preamble = messages[1]['content']
        assert (config.problem_dir / 'question.txt').read_text() in preamble
        assert f'<best_successful_advice>\n{advice}\n</best_successful_advice>' in preamble
        assert f'Best successful advice length: {length}' in preamble
        assert f'Turns without improvement: {streak}' in preamble
        assert messages[2]['content'] == (config.attempt_dir(attempt) / 'feedback.txt').read_text()
    assert json.dumps(FAIL) in chat_provider[4]['messages'][2]['content']
    transcript = [json.loads(line) for line in (config.u_transcripts / 'messages.jsonl').read_text().splitlines()]
    assert len(transcript) == 18  # system + four advice exchanges + three summary exchanges/preambles
    assert [m['content'] for m in transcript if m['role'] == 'assistant'] == [
        best, 'Failures: none. Best length is 999 (incorrect summary).', 'x',
        'Do not print zero.', 'double', 'Remember integer parsing.', 'longer advice',
    ]
    assert len(botbox_script.sessions) == 4
    assert not botbox_script.advice
    usage = [json.loads(line) for line in (config.u_transcripts / 'usage.jsonl').read_text().splitlines()]
    assert len(usage) == 7
    for entry in usage:
        assert entry['usage'] == USAGE
        assert entry['completion_id'] == 'test-chat'
        assert datetime.fromisoformat(entry['timestamp']).utcoffset().total_seconds() == 0
    for message in transcript + [m for request in chat_provider for m in request['messages']]:
        assert not ({'timestamp', 'usage', 'completion_id'} & message.keys())


async def test_leaves_history_intact_when_disabled(
    config, botbox_script, chat_provider,
):
    config.u_compact_chars = 0
    botbox_script.advice.extend(['first', 'second'])
    async with open_u_session(config, 'question') as session:
        await session.prompt('question')
        await session.prompt('feedback')
    assert len(chat_provider) == 2
    assert len(chat_provider[-1]['messages']) == 4


@pytest.mark.parametrize('over_by,expected_requests', [(0, 2), (1, 3)])
async def test_counts_reasoning_and_pending_feedback_at_the_threshold(
    config, botbox_script, chat_provider, over_by, expected_requests,
):
    botbox_script.advice.extend(['first', 'summary', 'second'])
    async with open_u_session(config, 'question') as session:
        await session.prompt('question')
        pending = 'feedback' * 100
        session.compact_chars = sum(
            len(m.get('content') or '') + len(m.get('reasoning') or '')
            for m in session.messages
        ) + len(pending) - over_by
        await session.prompt(pending)
    assert len(chat_provider) == expected_requests
    assert chat_provider[-1]['messages'][-1]['content'] == pending


async def test_compacts_with_the_measured_state_when_the_summary_request_fails(
    config, botbox_script, chat_provider, no_retry_wait,
):
    config.u_compact_chars = 1
    config.max_u_turns = 2
    botbox_script.advice.extend(['good', *[{'status': 400}] * 9, 'better'])
    botbox_script.solutions.extend([PASS, PASS])
    await run_experiment(config, on_delta=None)
    preamble = chat_provider[-1]['messages'][1]['content']
    assert '<prior_summary>\n(summary unavailable: U chat request failed' in preamble
    assert '<best_successful_advice>\ngood\n</best_successful_advice>' in preamble
    assert json.loads(config.result_file.read_text())['attempts'] == 2
    assert all(session.closed for session in botbox_script.sessions)


async def test_compaction_counts_reasoning_once(
    config, botbox_script, chat_provider,
):
    reasoning = 'r' * 210000
    details = [{'type': 'reasoning.text', 'index': 0, 'text': reasoning, 'format': 'unknown'}]
    botbox_script.advice.extend([
        {'deltas': [{'role': 'assistant', 'content': 'advice',
                     'reasoning': reasoning, 'reasoning_details': details}]},
        'next',
    ])
    async with open_u_session(config, 'question') as session:
        await session.prompt('question')
        assert session.compact_chars == 400000
        assert sum(len(json.dumps(m, ensure_ascii=False)) for m in session.messages) > 400000
        await session.prompt('feedback')
    assert len(chat_provider) == 2
    # Counting reasoning once must not strip either field from the next request.
    assistant = chat_provider[1]['messages'][2]
    assert assistant['reasoning'] == reasoning
    assert assistant['reasoning_details'] == details
    assert chat_provider[-1]['messages'][-1]['content'] == 'feedback'
