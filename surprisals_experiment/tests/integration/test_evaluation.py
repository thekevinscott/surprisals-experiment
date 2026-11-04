"""Real preflight and evaluator behavior, with only model and Botbox calls mocked."""
import json

import pytest
from botbox import RunResult

from conftest import FakeSession
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.run_test_suite import run_test_suite


async def test_invalid_suites_fail_before_starting_models(config, botbox_script, chat_provider):
    invalid = [None, {}, {'inputs': [], 'outputs': []},
               {'inputs': ['x', 'y'], 'outputs': ['x']},
               {'inputs': [[1]], 'outputs': ['1']},
               {'inputs': [''], 'outputs': ['7'], 'fn_name': 'answer'}]
    for suite in invalid:
        config.test_suite_file.write_text(json.dumps(suite))
        with pytest.raises(ValueError):
            await run_experiment(config, on_delta=None)
    config.test_suite_file.write_text('{')
    with pytest.raises(ValueError):
        await run_experiment(config, on_delta=None)
    assert not chat_provider
    assert not botbox_script.sessions


async def test_evaluator_cannot_drop_unmatched_cases(tmp_path):
    (tmp_path / 'main.py').write_text('print(7)')
    with pytest.raises(ValueError):
        await run_test_suite({'inputs': ['', ''], 'outputs': ['7']}, tmp_path)


async def test_wrong_crashing_and_binary_candidates_fail(tmp_path):
    sources = ['print(8)', 'raise RuntimeError("bad code")',
               "import os; os.write(1, b'\\xff')",
               "import os; os.write(2, b'\\xff'); print(7)"]
    for source in sources:
        (tmp_path / 'main.py').write_text(source)
        result_file = await run_test_suite({'inputs': [''], 'outputs': ['7']}, tmp_path)
        results = json.loads(result_file.read_text())
        assert not results['all_passed'], source
        assert results['passed'] == 0


async def test_missing_candidate_directory_is_an_evaluator_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        await run_test_suite({'inputs': [''], 'outputs': ['7']}, tmp_path / 'absent')


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
    assert json.loads((config.t_dir(0, 0) / 'run.json').read_text())['exit_code'] == 1


async def test_case_exceeding_five_seconds_fails(config, botbox_script):
    config.test_suite_file.write_text(json.dumps({'inputs': [''], 'outputs': ['done']}))
    botbox_script.advice.append('Print done.')
    botbox_script.solutions.append('import time; time.sleep(6); print("done")')
    assert await run_experiment(config, on_delta=None) is None
    result = json.loads((config.t_dir(0, 0) / 'tests.json').read_text())
    assert result['passed'] == 0
    assert result['cases'][0]['stderr'] == 'Test exceeded 5 seconds'
    assert result['duration_seconds'] >= 5


async def test_releases_each_case_before_running_the_next(tmp_path, monkeypatch):
    import importlib
    import weakref

    module = importlib.import_module('surprisals_experiment.sdk.run_test_suite.run_test_suite')
    original = module.run_case
    previous = None
    calls = 0

    async def track(*args):
        nonlocal previous, calls
        if previous is not None:
            assert previous() is None
        result = await original(*args)
        previous = weakref.ref(result)
        calls += 1
        return result

    monkeypatch.setattr(module, 'run_case', track)
    (tmp_path / 'main.py').write_text(
        'import sys\nsys.stdout.write("x" * 262144)\nsys.stderr.write("y" * 262144)\n'
    )
    path = await run_test_suite({'inputs': [''] * 3, 'outputs': ['x' * 262144] * 3}, tmp_path)
    assert calls == 3
    assert previous() is None
    saved = json.loads(path.read_text())
    assert saved['passed'] == 3
    assert len(saved['cases']) == 3
    assert all(case['stdout'] == 'x' * 262144 and case['stderr'] == 'y' * 262144
               for case in saved['cases'])
