import asyncio
import importlib
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from adocker import DockerException

module = importlib.import_module('surprisals_experiment.sdk.utils.botbox_session')


@pytest.fixture(autouse=True)
def entry_harness(monkeypatch):
    state = {'entries': 0, 'exits': 0, 'bodies': 0, 'failures': [], 'box_exits': 0}
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, 'sleep', sleep)
    state['sleep'] = sleep

    class Box:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            state['box_exits'] += 1

        @asynccontextmanager
        async def session(self, **kwargs):
            state['entries'] += 1
            if state['failures']:
                raise state['failures'].pop(0)
            try:
                yield state
            finally:
                state['exits'] += 1

    monkeypatch.setattr(module, 'Botbox', Box)
    return state


def session():
    return module.botbox_session(None, dockerfile=None, mounts=[], workdir=None, output=None)


def docker_error(text='DeadlineExceeded: context deadline exceeded'):
    return DockerException(['docker', 'buildx', 'build'], 1, text)


def describe_botbox_entry():
    async def it_retries_deadline_exceeded_before_running_body_once(entry_harness):
        state = entry_harness
        state['failures'] = [docker_error()]
        async with session():
            state['bodies'] += 1
        assert (state['entries'], state['bodies'], state['exits'], state['box_exits']) == (2, 1, 1, 2)
        state['sleep'].assert_awaited_once_with(10)

    @pytest.mark.parametrize('text', ['permission denied', 'context deadline exceeded'])
    async def it_does_not_retry_other_docker_errors(entry_harness, text):
        error = docker_error(text)
        entry_harness['failures'] = [error]
        with pytest.raises(DockerException) as caught:
            async with session():
                pytest.fail('body must not run')
        assert caught.value is error
        assert entry_harness['entries'] == 1
        entry_harness['sleep'].assert_not_awaited()

    async def it_never_retries_a_body_failure(entry_harness):
        with pytest.raises(DockerException):
            async with session():
                entry_harness['bodies'] += 1
                raise docker_error()
        assert (entry_harness['entries'], entry_harness['bodies'], entry_harness['exits']) == (1, 1, 1)
        entry_harness['sleep'].assert_not_awaited()

    async def it_reports_exhaustion(entry_harness):
        entry_harness['failures'] = [docker_error()] * 9
        with pytest.raises(RuntimeError, match=r'botbox.*DeadlineExceeded.*8 retries exhausted'):
            async with session():
                pytest.fail('body must not run')
        assert entry_harness['entries'] == 9
        assert entry_harness['box_exits'] == 9
        assert [c.args[0] for c in entry_harness['sleep'].await_args_list] == [10,30,60,120,300,600,1800,3600]
