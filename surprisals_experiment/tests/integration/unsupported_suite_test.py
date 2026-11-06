"""Problems whose test suite the evaluator cannot run are refused before U is asked."""

import json

import pytest

from utils.world import Done


@pytest.mark.parametrize('suite,reason', [
    pytest.param({'inputs': [], 'outputs': []}, 'it has no test cases', id='empty'),
    pytest.param({'fn_name': 'reverse', 'inputs': [['the sky is blue']], 'outputs': ['blue is sky the']},
                 'it has fn_name', id='fn-name'),
    pytest.param({'inputs': [['0']], 'outputs': [['yes']]}, 'it has non-string inputs or outputs', id='list-valued'),
])
async def test_refuses_unsupported_suite(config, execute_run_experiment, suite, reason):
    io = config.problem_dir / 'input_output.json'
    io.write_text(json.dumps(suite))
    async with execute_run_experiment(config, [
            Done(outcome=ValueError(f'{io} is not a stdin/stdout test suite: {reason}'))]):
        pass
    assert not config.output.exists()
