"""Real preflight and evaluator behavior, with only model and Botbox calls mocked."""
import json

from botbox import RunResult

from conftest import FakeSession
from run_one_window import run_one_window


async def test_nonzero_t_exit_can_produce_valid_solution_and_duration(config, botbox_script, monkeypatch):
    botbox_script.advice.append('Double it.')
    botbox_script.solutions.append('print(int(input()) * 2)')
    original = FakeSession.close

    def close(self):
        original(self)
        return RunResult(exit_code=1)

    monkeypatch.setattr(FakeSession, 'close', close)
    assert await run_one_window(config, on_delta=None) == config.t_dir(0, 0) / 'src'
    result = json.loads((config.t_dir(0, 0) / 'tests.json').read_text())
    assert result['all_passed']
    assert isinstance(result['duration_seconds'], float)
    assert result['duration_seconds'] >= 0
    assert json.loads((config.t_dir(0, 0) / 'generation.json').read_text())['exit_code'] == 1


async def test_case_exceeding_five_seconds_fails(config, botbox_script):
    (config.problem_dir / 'input_output.json').write_text(json.dumps({'inputs': [''], 'outputs': ['done']}))
    botbox_script.advice.append('Print done.')
    botbox_script.solutions.append('import time; time.sleep(6); print("done")')
    assert await run_one_window(config, on_delta=None) is None
    result = json.loads((config.t_dir(0, 0) / 'tests.json').read_text())
    assert result['passed'] == 0
    assert result['cases'][0]['stderr'] == 'Test exceeded 5 seconds'
    assert result['duration_seconds'] >= 5
