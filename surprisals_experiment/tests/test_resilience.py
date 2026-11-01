"""A single failure anywhere in a turn is retried; the run does not exit."""

import asyncio
import importlib
import json
from unittest.mock import AsyncMock

import httpx2
import pytest
from adocker import DockerException
from openai import APIStatusError

from surprisals_experiment.config import Config
from surprisals_experiment.sdk import run_experiment

PASS = 'print(int(input())*2)'


@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, 'sleep', sleep)
    return sleep


async def completes(config, no_retry_wait):
    assert await run_experiment(config, on_delta=None) == config.t_dir(0, 0) / 'src'
    no_retry_wait.assert_awaited_once_with(10)


def describe_u_chat():
    @pytest.mark.parametrize('failure', [
        pytest.param({'deltas': [{'role': 'assistant', 'reasoning': 'Hmm: what about'}], 'finish': 'stop'},
                     id='seen:thinking-only-stop'),
        pytest.param({'deltas': [{'role': 'assistant', 'content': 'partial'}], 'finish': 'content_filter'},
                     id='seen:content-filter'),
        pytest.param({'deltas': [{'role': 'assistant', 'content': 'partial'}], 'finish': 'tool_calls'},
                     id='unknown-finish-reason'),
        *[pytest.param({'status': code}, id=f'status-{code}') for code in (400, 404, 408, 409)],
        pytest.param({'deltas': [{'role': 'assistant', 'content': 'partial'}], 'finish': None,
                      'stream_error': {'code': 'upstream_error', 'message': 'Provider returned error'}},
                     id='stream-error-string-code'),
        pytest.param({'deltas': [{'role': 'assistant', 'content': 'partial'}], 'finish': None,
                      'stream_error': {'code': 400, 'message': 'Provider returned error'}},
                     id='stream-error-400'),
    ])
    async def it_retries_a_failed_reply(config, botbox_script, no_retry_wait, failure):
        botbox_script.advice.extend([failure, 'Use a loop'])
        botbox_script.solutions.append(PASS)
        await completes(config, no_retry_wait)

    async def it_does_not_exit_when_u_exhausts_its_output_limit_retries(config, botbox_script):
        # seen: U loops until 131k tokens on every attempt.
        config.max_u_turns = 2
        botbox_script.advice.extend([{'deltas': [{'role': 'assistant', 'content': 'partial'}],
                                      'finish': 'length'}] * 9 + ['Use a loop'])
        botbox_script.solutions.append(PASS)
        await run_experiment(config, on_delta=None)


def describe_t_botbox():
    @pytest.fixture
    def entry_failure(monkeypatch):
        module = importlib.import_module('surprisals_experiment.sdk.utils.botbox_session')
        failures = []

        class FailingEntry(module.Botbox):
            def session(self, **kwargs):
                if failures:
                    raise failures.pop(0)
                return super().session(**kwargs)

        monkeypatch.setattr(module, 'Botbox', FailingEntry)
        return failures

    @pytest.mark.parametrize('failure', [
        pytest.param(RuntimeError('botbox credential proxy did not start:\n'), id='seen:credential-proxy'),
        pytest.param(RuntimeError('botbox proxy did not start:\n'), id='egress-proxy'),
        *[pytest.param(DockerException(['docker'], 1, text), id=text) for text in (
            'Error response from daemon: No such container: botbox-credentials-1',
            'Error response from daemon: remove botbox-run-1: volume is in use',
            'Cannot connect to the Docker daemon at unix:///var/run/docker.sock',
            'net/http: TLS handshake timeout',
        )],
    ])
    async def it_retries_a_failed_entry(config, botbox_script, no_retry_wait, entry_failure, failure):
        entry_failure.append(failure)
        botbox_script.advice.append('Use a loop')
        botbox_script.solutions.append(PASS)
        await completes(config, no_retry_wait)

    @pytest.mark.parametrize('failure', [
        pytest.param(DockerException(['docker'], 137, 'container killed'), id='container-killed'),
        pytest.param(RuntimeError('pi exited before agent_settled'), id='agent-crash'),
    ])
    async def it_retries_a_failed_sample(config, botbox_script, no_retry_wait, failure):
        botbox_script.advice.append('Use a loop')
        botbox_script.solutions.extend([failure, PASS])
        await completes(config, no_retry_wait)


def describe_scorer():
    @pytest.mark.parametrize('failure', [
        *[pytest.param(APIStatusError('scorer failed', body=None, response=httpx2.Response(
            code, request=httpx2.Request('POST', 'http://scorer/v1/completions'))), id=f'status-{code}')
          for code in (400, 404, 408)],
        pytest.param(json.JSONDecodeError('Expecting value', '', 0), id='malformed-body'),
    ])
    async def it_retries_a_failed_score(config, botbox_script, monkeypatch, no_retry_wait, failure):
        config = Config(**(config.model_dump() | {
            'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1'}))
        scorer = AsyncMock(side_effect=[failure, [('Use a loop', 10.0)]])
        monkeypatch.setattr(importlib.import_module('surprisals_experiment.sdk.advice_measure'),
                            'measure_surprisal', scorer)
        botbox_script.advice.append('Use a loop')
        botbox_script.solutions.append(PASS)
        await completes(config, no_retry_wait)
