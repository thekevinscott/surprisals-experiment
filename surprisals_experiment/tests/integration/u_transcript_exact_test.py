"""Every line of a U transcript file is exactly what U was sent, across turns and retries."""

import json
from unittest.mock import patch

import pytest

from state_machine.testing import State
from u_flush_test import PASS, QUESTION, flush, outcome, played
from utils.mock_llm import MockLLM
from utils.world import U

TURN = 'windows/0/forks/0/turns/0'
TRANSCRIPT = 'windows/{}/forks/0/u/transcript.jsonl'


@pytest.fixture
def run_and_record(config, execute_run_experiment):
    answer = MockLLM.answer
    sent = []

    async def recording(self, kind, request):
        if kind is U:
            sent.append([dict(message) for message in request['messages']])
        return await answer(self, kind, request)

    async def run(world):
        async with execute_run_experiment(config, world):
            pass
        return sent

    with patch.object(MockLLM, 'answer', recording):
        yield run


def lines(config, window):
    path = config.output / TRANSCRIPT.format(window)
    return [{key: entry[key] for key in ('role', 'content')} for entry in map(json.loads, path.read_text().splitlines())]


def assert_exact(file, requests):
    for request in requests:
        assert request == file[:len(request)]
    assert len(file) == len(requests[-1]) + 2
    assert file[-2]['role'] == 'assistant'
    assert file[-1]['role'] == 'user'
    assert file[-1]['content'].startswith('<advice_length>')


async def test_multi_turn_transcript_is_exactly_what_u_was_sent(config, run_and_record):
    config.max_u_turns = 2
    windows = [
        [(QUESTION, 'double it', [PASS]), (None, 'double it', [PASS])],
        [(flush(0, 'double it', length=9), 'double', [PASS]), (None, 'double', [PASS])],
        [(flush(0, 'double', length=6), 'ok', [PASS]), (None, 'ok', [PASS])],
        [(flush(0, 'ok', length=2), 'ok', [PASS]), (None, 'ok', [PASS])],
    ]
    world, pending = played(windows, {'double it': {'score': 9}, 'double': {'score': 6}, 'ok': {'score': 2}}, config=config)
    world.append(outcome(config, 'windows/2/forks/0/turns/0', 8, pending))
    sent = await run_and_record(world)
    assert len(sent) == 8
    for window in range(4):
        assert_exact(lines(config, window), sent[2 * window:2 * window + 2])


async def test_interrupted_reply_is_not_in_the_transcript(config, run_and_record):
    config.max_u_turns = 2
    windows = [
        [(QUESTION, 'Use a loop', [PASS]), (None, 'Use a loop', [PASS])],
        [(flush(0, 'Use a loop', length=10), 'Use a loop', [PASS]), (None, 'Use a loop', [PASS])],
    ]
    world, pending = played(windows, {'Use a loop': {'score': 10}}, config=config)
    retried = world[0]
    failed = State(U('partial', finish=None, drop=True), sent=retried.sent,
                   logs=[(f'{TURN}/u', 'text', 'partial')], files=retried.files)
    retried.logs = [(f'{TURN}/u', 'retry', '1/8 in 10s: Connection error.\n'), *retried.logs]
    retried.files = {}
    world = [failed, *world, outcome(config, TURN, 4, pending)]
    sent = await run_and_record(world)
    assert len(sent) == 5
    assert sent[0] == sent[1]
    assert_exact(lines(config, 0), sent[1:3])
    assert_exact(lines(config, 1), sent[3:])


async def test_failed_reply_usage_goes_to_the_run_log(config, run_and_record):
    usage = {'completion_tokens': 20, 'prompt_tokens': 10, 'total_tokens': 30}
    config.max_u_turns = 2
    windows = [
        [(QUESTION, 'Use a loop', [PASS]), (None, 'Use a loop', [PASS])],
        [(flush(0, 'Use a loop', length=10), 'Use a loop', [PASS]), (None, 'Use a loop', [PASS])],
    ]
    world, pending = played(windows, {'Use a loop': {'score': 10}}, config=config)
    retried = world[0]
    failed = State(U('partial', finish=None, drop=True, usage=usage), sent=retried.sent,
                   logs=[(f'{TURN}/u', 'text', 'partial')],
                   files=retried.files)
    retried.logs = [(f'{TURN}/u', 'usage', json.dumps(usage)),
                    (f'{TURN}/u', 'retry', '1/8 in 10s: Connection error.\n'), *retried.logs]
    retried.files = {}
    world = [failed, *world, outcome(config, TURN, 4, pending)]
    sent = await run_and_record(world)
    assert_exact(lines(config, 0), sent[1:3])


async def test_reasoning_is_saved_but_never_sent_back(config, run_and_record):
    config.max_u_turns = 2
    windows = [
        [(QUESTION, 'double it', [PASS]), (None, 'double it', [PASS])],
        [(flush(0, 'double it', length=9), 'double', [PASS]), (None, 'double', [PASS])],
        [(flush(0, 'double', length=6), 'ok', [PASS]), (None, 'ok', [PASS])],
        [(flush(0, 'ok', length=2), 'ok', [PASS]), (None, 'ok', [PASS])],
    ]
    world, pending = played(windows, {'double it': {'score': 9}, 'double': {'score': 6}, 'ok': {'score': 2}}, config=config)
    world.append(outcome(config, 'windows/2/forks/0/turns/0', 8, pending))
    sent = await run_and_record(world)
    for window in range(4):
        path = config.output / TRANSCRIPT.format(window)
        replies = [entry for entry in map(json.loads, path.read_text().splitlines()) if entry['role'] == 'assistant']
        assert len(replies) == 2
        assert all(reply['reasoning'] == 'Think.' for reply in replies)
    assert any(message['role'] == 'assistant' for request in sent for message in request)
    for request in sent:
        for message in request:
            assert set(message) == {'role', 'content'}, message
            assert 'Think.' not in message['content']
