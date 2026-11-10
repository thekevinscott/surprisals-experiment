"""Real Docker/Pi tests, explicitly invoked and never run in CI."""

import os

import pytest

from surprisals_experiment.config import SCORER_MODEL, T_MODEL, T_PROVIDERS, U_MODEL, U_PROVIDER, Config


@pytest.fixture(autouse=True)
def local_only():
    if os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
        pytest.skip('E2E tests are local/remote manual checks, excluded from CI')


@pytest.fixture
def config(tmp_path):
    return Config(
        api_key='unused-no-provider-calls', problem_dir=tmp_path / 'problem',
        output=tmp_path / 'run', u_model=U_MODEL, u_provider=U_PROVIDER, t_model=T_MODEL,
        t_provider=T_PROVIDERS[T_MODEL], scorer_model=SCORER_MODEL,
        u_thinking='off', t_samples=1, max_u_turns=1,
    )
