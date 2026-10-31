import asyncio
import importlib
from unittest.mock import AsyncMock

import pytest
from adocker import DockerException

module = importlib.import_module('surprisals_experiment.sdk.utils.botbox_run')


@pytest.fixture
def box(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, 'sleep', sleep)

    class Box:
        builds = 0
        failures = []
        wait = sleep

        async def build(self):
            Box.builds += 1
            if Box.failures:
                raise Box.failures.pop(0)
            return 'tag'

    return Box()


def docker_error(text='DeadlineExceeded: context deadline exceeded'):
    return DockerException(['docker', 'buildx', 'build'], 1, text)


def describe_botbox_build():
    async def it_retries_deadline_exceeded(box):
        box.failures.append(docker_error())
        assert await module.build(box) == 'tag'
        assert box.builds == 2
        box.wait.assert_awaited_once_with(10)

    @pytest.mark.parametrize('text', ['permission denied', 'context deadline exceeded'])
    async def it_does_not_retry_other_docker_errors(box, text):
        error = docker_error(text)
        box.failures.append(error)
        with pytest.raises(DockerException) as caught:
            await module.build(box)
        assert caught.value is error
        assert box.builds == 1
        box.wait.assert_not_awaited()

    async def it_reports_exhaustion(box):
        box.failures.extend([docker_error()] * 9)
        with pytest.raises(RuntimeError, match=r'botbox.*DeadlineExceeded.*8 retries exhausted'):
            await module.build(box)
        assert box.builds == 9
        assert [c.args[0] for c in box.wait.await_args_list] == [10, 20, 30, 60, 180, 300, 1200, 1800]
