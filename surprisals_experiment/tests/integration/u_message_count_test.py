"""Turn metadata identifies the exact transcript prefix sent for its accepted advice."""

import json
from unittest.mock import patch

import pytest
from state_machine.testing import State
from u_flush_test import PASS, QUESTION, flush, outcome, played
from utils.mock_llm import MockLLM
from utils.world import U


@pytest.fixture
def u_requests():
    answer = MockLLM.answer
    requests = []

    async def recording(self, kind, sent):
        if kind is U:
            requests.append(json.loads(json.dumps(sent)))
        return await answer(self, kind, sent)

    with patch.object(MockLLM, 'answer', recording):
        yield requests


async def test_each_turn_records_the_sent_message_count_and_exact_prefix(config, execute_run_experiment, u_requests):
    config.max_u_turns = 2
    world, pending = played([
        [(QUESTION, 'double', [PASS]), (None, 'double', [PASS])],
        [(flush(0, 'double', length=6), 'double', [PASS]), (None, 'double', [PASS])],
    ], {'double': {'score': 6}}, config=config)
    retried = world[2]
    failed = State(U(status=400), sent=retried.sent, files=retried.files)
    retried.files = {}
    retried.logs.insert(0, ('windows/0/forks/0/turns/1/u', 'retry',
                           "1/8 in 10s: Error code: 400 - {'error': {'message': 'provider failed'}}\n"))
    world.insert(2, failed)
    world.append(outcome(config, 'windows/0/forks/0/turns/0', 4, pending))
    async with execute_run_experiment(config, world):
        pass

    assert len(u_requests) == 5
    assert u_requests[1]['messages'] == u_requests[2]['messages']
    for (window, turn), request in zip([(0, 0), (0, 1), (1, 0), (1, 1)],
                                       [u_requests[index] for index in (0, 2, 3, 4)], strict=True):
        fork = config.output / f'windows/{window}/forks/0'
        metadata = json.loads((fork / f'turns/{turn}/metadata.json').read_text())
        assert metadata['u_messages'] == len(request['messages'])
        entries = [json.loads(line) for line in (fork / 'u/transcript.jsonl').read_text().splitlines()]
        assert [{key: entry[key] for key in ('role', 'content')}
                for entry in entries[:metadata['u_messages']]] == request['messages']
