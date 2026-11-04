"""Real preflight and evaluator behavior, with only model and Botbox calls mocked."""
import json

import pytest
from botbox import RunResult

from conftest import FakeSession
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.run_test_suite import run_test_suite_for_t


async def test_wrong_crashing_and_binary_candidates_fail(tmp_path):
    sources = ['print(8)', 'raise RuntimeError("bad code")',
               "import os; os.write(1, b'\\xff')",
               "import os; os.write(2, b'\\xff'); print(7)"]
    for source in sources:
        (tmp_path / 'main.py').write_text(source)
        results = await run_test_suite_for_t([{'input': '', 'output': '7'}], tmp_path)
        assert not results.all_passed, source
        assert results.passed == 0


async def test_missing_candidate_directory_is_an_evaluator_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        await run_test_suite_for_t([{'input': '', 'output': '7'}], tmp_path / 'absent')


async def test_nonzero_t_exit_can_produce_valid_solution_and_duration(config, botbox_script, monkeypatch):
    botbox_script.advice.append('Double it.')
    botbox_script.solutions.append('print(int(input()) * 2)')
    original = FakeSession.close

    def close(self):
        original(self)
        return RunResult(exit_code=1)

    monkeypatch.setattr(FakeSession, 'close', close)
    assert await run_experiment(config, on_delta=None) == config.t_dir(0, 0) / 'src'
    result = json.loads((config.t_dir(0, 0) / 'tests.json').read_text())
    assert result['all_passed']
    assert isinstance(result['duration_seconds'], float)
    assert result['duration_seconds'] >= 0
    assert json.loads((config.t_dir(0, 0) / 'generation.json').read_text())['exit_code'] == 1


async def test_case_exceeding_five_seconds_fails(config, botbox_script):
    (config.problem_dir / 'input_output.json').write_text(json.dumps({'inputs': [''], 'outputs': ['done']}))
    botbox_script.advice.append('Print done.')
    botbox_script.solutions.append('import time; time.sleep(6); print("done")')
    assert await run_experiment(config, on_delta=None) is None
    result = json.loads((config.t_dir(0, 0) / 'tests.json').read_text())
    assert result['passed'] == 0
    assert result['cases'][0]['stderr'] == 'Test exceeded 5 seconds'
    assert result['duration_seconds'] >= 5
