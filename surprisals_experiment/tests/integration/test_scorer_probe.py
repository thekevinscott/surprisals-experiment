import asyncio
import json
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx2
import pytest
from openai import AsyncOpenAI
from surprisals_experiment.cli.scorer_probe import probe
from surprisals_experiment.cli.scorer_probe.main import main
from surprisals_experiment.config import T_MODEL
from surprisals_experiment.sdk.advice_measure import AdviceMeasure

ENDPOINT = 'https://test-pod-8000.proxy.runpod.net/v1'


@pytest.fixture
def probe_http():
    state = SimpleNamespace(requests=[], clients=[], models=[T_MODEL], failure=None,
                            active=0, peak=0, concurrency=1, together=asyncio.Event())

    async def respond(request):
        state.requests.append(request)
        if request.url.path == '/v1/models':
            return httpx2.Response(200, json={'data': [{'id': model} for model in state.models]})
        assert request.url.path == '/v1/completions'
        state.active += 1
        state.peak = max(state.peak, state.active)
        try:
            if state.active == state.concurrency:
                state.together.set()
            await asyncio.wait_for(state.together.wait(), 5)
            if state.failure == 'timeout':
                raise httpx2.ReadTimeout('mock scorer timed out', request=request)
            if state.failure == 'unauthorized':
                return httpx2.Response(401, json={'error': {'message': 'mock unauthorized'}})
            logprobs = None if state.failure == 'logprobs' else {
                'tokens': ['ca', 'fé', '\n'], 'token_logprobs': [None, -math.log(2), -2 * math.log(2)],
                'text_offset': [0, 2, 4],
            }
            return httpx2.Response(200, json={
                'id': 'score', 'object': 'text_completion', 'created': 1, 'model': T_MODEL,
                'choices': [{'index': 0, 'text': 'café\n', 'finish_reason': 'length', 'logprobs': logprobs}],
            })
        finally:
            state.active -= 1

    def client(**kwargs):
        result = AsyncOpenAI(**kwargs,
                            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)))
        state.clients.append(result)
        return result

    with patch('measure_surprisal.utils.client.AsyncOpenAI', client):
        yield state


async def test_probe_matches_experiment_request_and_bounds_concurrency(probe_http):
    measure = AdviceMeasure('surprisal', base_url=ENDPOINT, model=T_MODEL)
    try:
        await measure.score('café\n')
    finally:
        await measure.client._openai.close()
    baseline = probe_http.requests.pop()
    probe_http.concurrency = 3
    probe_http.together.clear()
    result = await probe(ENDPOINT, 'café\n', concurrency=3, requests=6)
    assert probe_http.peak == 3
    assert result['model'] == T_MODEL
    assert result['succeeded'] == 6 and result['failed'] == 0
    assert result['scores_per_second'] > 0
    assert result['tokens_per_second'] == pytest.approx(3 * result['scores_per_second'])
    assert result['timeout_seconds'] == {'connect': 5, 'read': 600, 'write': 600, 'pool': 600}
    assert len(probe_http.requests) == 7
    for request in probe_http.requests:
        assert request.headers['authorization'] == 'Bearer EMPTY'
        assert request.headers['user-agent'] == baseline.headers['user-agent']
        assert 'Mozilla' in request.headers['user-agent']
        assert request.extensions['timeout'] == result['timeout_seconds']
    for request in probe_http.requests[1:]:
        assert json.loads(request.content) == json.loads(baseline.content) == {
            'model': T_MODEL, 'prompt': 'café\n', 'max_tokens': 0,
            'echo': True, 'logprobs': 1, 'temperature': 0,
        }
    assert all(row['bits'] == pytest.approx(3) and row['tokens'] == 3 for row in result['results'])
    assert all(client.is_closed() and client.max_retries == 0 for client in probe_http.clients)


async def test_wrong_model_stops_before_scoring(probe_http):
    probe_http.models = ['some-other-model']
    with pytest.raises(ValueError, match='does not serve openai/gpt-oss-120b'):
        await probe(ENDPOINT, 'café\n', concurrency=1, requests=1)
    assert len(probe_http.requests) == 1
    assert probe_http.clients[0].is_closed()


@pytest.mark.parametrize('failure', ['timeout', 'unauthorized', 'logprobs'])
async def test_cli_reports_exhausted_failures_and_exits_nonzero(probe_http, tmp_path, capsys, failure):
    probe_http.failure = failure
    prompt = tmp_path / 'advice.txt'
    prompt.write_text('café\n')
    with patch('asyncio.sleep', new_callable=AsyncMock) as sleep, pytest.raises(SystemExit) as raised:
        await main([ENDPOINT, str(prompt), '--requests', '1'])
    assert raised.value.code == 1
    result = json.loads(capsys.readouterr().out)
    assert result['succeeded'] == 0 and result['failed'] == 1
    assert result['scores_per_second'] == result['tokens_per_second'] == 0
    assert '8 retries exhausted' in result['results'][0]['error']
    assert len(probe_http.requests) == 10
    assert sleep.await_count == 8
    assert probe_http.clients[0].is_closed()


async def test_cli_success_and_invalid_concurrency(probe_http, tmp_path, capsys):
    prompt = tmp_path / 'advice.txt'
    prompt.write_bytes('café\n'.encode())
    await main([ENDPOINT, str(prompt), '--requests', '2', '--concurrency', '2'])
    assert json.loads(capsys.readouterr().out)['succeeded'] == 2
    before = len(probe_http.requests)
    with pytest.raises(SystemExit) as raised:
        await main([ENDPOINT, str(prompt), '--concurrency', '0'])
    assert raised.value.code == 2
    assert len(probe_http.requests) == before
