"""Shared config and retry fixtures."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from surprisals_experiment.config import Config

pytest.register_assert_rewrite('utils')


@pytest.fixture
def no_retry_wait(monkeypatch):
    waits = AsyncMock()
    real_sleep = asyncio.sleep

    # Retry waits are 10 s and up; shorter sleeps are polls that must yield.
    async def sleep(delay, *args, **kwargs):
        if delay >= 1:
            return await waits(delay)
        return await real_sleep(delay, *args, **kwargs)

    monkeypatch.setattr(asyncio, "sleep", sleep)
    return waits


@pytest.fixture(autouse=True)
def config(tmp_path):
    problem = tmp_path / "problem"
    problem.mkdir()
    (problem / "question.txt").write_text("Read an integer and print its double.")
    (problem / "input_output.json").write_text(
        json.dumps(
            {
                "inputs": ["3\n", "7\n"],
                "outputs": ["6\n", "14\n"],
            }
        )
    )
    return Config(
        api_key="test-key",
        problem_dir=problem,
        output=tmp_path / "run",
        u_model="u",
        t_model="t",
        t_samples=1,
        u_thinking="high",
        max_u_turns=1,
        window_forks=1,
    )


@pytest.fixture
def execute_run_experiment():
    # utils sits in tests/integration, which is on sys.path only once a test module there is collected.
    from utils.execute_run_experiment import execute_run_experiment
    return execute_run_experiment
