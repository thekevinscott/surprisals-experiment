import pytest

pytest.register_assert_rewrite('utils')

from utils.execute_run_experiment import execute_run_experiment as run  # noqa: E402


@pytest.fixture
def execute_run_experiment():
    return run
