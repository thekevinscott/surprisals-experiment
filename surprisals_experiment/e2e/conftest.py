"""Real Docker/Pi tests, explicitly invoked and never run in CI."""

import os

import pytest

from surprisals_experiment.config import Config, U_MODEL, T_MODEL


@pytest.fixture(autouse=True)
def local_only():
    if os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
        pytest.skip('E2E tests are local/remote manual checks, excluded from CI')


@pytest.fixture
def config(tmp_path):
    return Config(
        api_key='unused-no-provider-calls', problem_dir=tmp_path / 'problem',
        output=tmp_path / 'run', u_model=U_MODEL, t_model=T_MODEL,
        u_thinking='off', t_samples=1, max_u_turns=1, test_timeout_seconds=5,
    )
