"""Turn metadata identifies the exact transcript prefix sent for its accepted advice."""

import json
from hashlib import sha256
from unittest.mock import patch

import httpx2
import pytest
from state_machine.testing import State
from u_flush_test import PASS, QUESTION, appended, flush, outcome, played
from utils.world import U, u_user
from surprisals_experiment.config import Config


@pytest.fixture
def u_requests():
    handle = httpx2.MockTransport.handle_async_request
    requests = []

    async def recording(self, request):
        if json.loads(request.content).get("model") == "u":
            requests.append(request.content)
        return await handle(self, request)

    with patch.object(httpx2.MockTransport, 'handle_async_request', recording):
        yield requests


@pytest.mark.parametrize('measure', ['characters', 'surprisal'])
async def test_each_turn_records_the_sent_request_hash_message_count_and_exact_prefix(config, execute_run_experiment, u_requests, measure):
    config = Config(**(config.model_dump() | {
        'cap_strategy': measure, 'scorer_base_url': 'http://scorer/v1', 'max_u_turns': 2,
    }))
    tokens = [('dou', 1.125), ('ble', 2.625)]
    bits = {'double': tokens} if measure == 'surprisal' else {}
    score = {'score': 3.75, 'tokens': [list(pair) for pair in tokens]} if bits else {'score': 6}
    expected = ('<advice_surprisal_bits>\n<total>3.75</total>\n<token bits="1.12">"dou"</token>\n'
                '<token bits="2.62">"ble"</token>\n</advice_surprisal_bits>') if bits else '<advice_length>6 characters</advice_length>'
    best = flush(0, 'double', bits=tokens) if bits else flush(0, 'double', length=6)
    world, pending = played([
        [(QUESTION, 'double', [PASS]), (None, 'double', [PASS])],
        [(best, 'double', [PASS]), (None, 'double', [PASS])],
    ], {'double': score}, bits=bits, config=config)
    retried = [state for state in world if isinstance(state.reply, U)][1]
    failed = State(U(status=400), sent=retried.sent, files=retried.files)
    retried.files = {}
    retried.logs.insert(0, ('windows/0/forks/0/turns/1/u', 'retry',
                           "1/8 in 10s: Error code: 400 - {'error': {'message': 'provider failed'}}\n"))
    world.insert(world.index(retried), failed)
    scoring = {'best_measurement': 3.75, 'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1',
               'scorer_model': 'openai/gpt-oss-120b'} if bits else {}
    world.append(outcome(config, 'windows/0/forks/0/turns/0', 4, pending, **scoring))
    async with execute_run_experiment(config, world):
        pass

    assert len(u_requests) == 5
    assert all(json.loads(body)['model'] == 'u' for body in u_requests)
    assert json.loads(u_requests[1])['messages'] == json.loads(u_requests[2])['messages']
    for (window, turn), request_bytes in zip([(0, 0), (0, 1), (1, 0), (1, 1)],
                                       [u_requests[index] for index in (0, 2, 3, 4)], strict=True):
        request = json.loads(request_bytes)
        assert request['messages'][1] == {'role': 'user', 'content': QUESTION if window == 0 else best}
        assert request['messages'][2] == {
            'role': 'user', 'content': u_user(config, 1, best=None if window == 0 else score['score']),
        }
        fork = config.output / f'windows/{window}/forks/0'
        metadata = json.loads((fork / f'turns/{turn}/metadata.json').read_text())
        assert metadata['u_request_sha256'] == sha256(request_bytes).hexdigest()
        assert metadata['u_messages'] == len(request['messages'])
        entries = [json.loads(line) for line in (fork / 'u/transcript.jsonl').read_text().splitlines()]
        assert [{key: entry[key] for key in ('role', 'content')}
                for entry in entries[:metadata['u_messages']]] == request['messages']

        assert entries[metadata['u_messages'] + 1] == {
            'role': 'user', 'content': expected,
        }
        if turn:
            assert request['messages'][-3] == {
                'role': 'user', 'content': expected,
            }
            assert request['messages'][-2] == {'role': 'user', 'content': appended(PASS)}
            assert request['messages'][-1] == {
                'role': 'user', 'content': u_user(config, turn + 1, best=None if window == 0 else score['score']),
            }
