import pytest

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


async def test_case_exceeding_five_seconds_fails(tmp_path):
    (tmp_path / 'main.py').write_text('import time; time.sleep(6); print("done")')
    results = await run_test_suite_for_t([{'input': '', 'output': 'done'}], tmp_path)
    assert results.passed == 0
    assert results.cases[0].stderr == 'Test exceeded 5 seconds'


async def test_case_exceeding_the_memory_budget_fails_and_the_suite_continues(tmp_path):
    (tmp_path / 'main.py').write_text("if input() == 'big':\n    x = bytearray(1 << 30)\nprint('done')\n")
    results = await run_test_suite_for_t(
        [{'input': 'big', 'output': 'done'}, {'input': 'small', 'output': 'done'}], tmp_path)
    assert [case.passed for case in results.cases] == [False, True]
    assert 'MemoryError' in results.cases[0].stderr
