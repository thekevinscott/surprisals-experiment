"""Turn metadata identifies the exact transcript prefix sent for its accepted advice."""

import json
from hashlib import sha256
from unittest.mock import patch

import httpx2
import pytest
from state_machine.testing import State
from u_flush_test import PASS, QUESTION, flush, outcome, played
from utils.world import U


@pytest.fixture
def u_requests():
    handle = httpx2.MockTransport.handle_async_request
    requests = []

    async def recording(self, request):
        requests.append(request.content)
        return await handle(self, request)

    with patch.object(httpx2.MockTransport, 'handle_async_request', recording):
        yield requests


async def test_each_turn_records_the_sent_request_hash_message_count_and_exact_prefix(config, execute_run_experiment, u_requests):
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
    assert all(json.loads(body)['model'] == 'u' for body in u_requests)
    assert json.loads(u_requests[1])['messages'] == json.loads(u_requests[2])['messages']
    for (window, turn), request_bytes in zip([(0, 0), (0, 1), (1, 0), (1, 1)],
                                       [u_requests[index] for index in (0, 2, 3, 4)], strict=True):
        request = json.loads(request_bytes)
        fork = config.output / f'windows/{window}/forks/0'
        metadata = json.loads((fork / f'turns/{turn}/metadata.json').read_text())
        assert metadata['u_request_sha256'] == sha256(request_bytes).hexdigest()
        assert metadata['u_messages'] == len(request['messages'])
        entries = [json.loads(line) for line in (fork / 'u/transcript.jsonl').read_text().splitlines()]
        assert [{key: entry[key] for key in ('role', 'content')}
                for entry in entries[:metadata['u_messages']]] == request['messages']

        assert entries[metadata['u_messages'] + 1] == {
            'role': 'user', 'content': '<advice_length>6 characters</advice_length>',
        }
        if turn:
            assert request['messages'][-2] == {
                'role': 'user', 'content': '<advice_length>6 characters</advice_length>',
            }
            assert '<advice_length>' not in request['messages'][-1]['content']
