import json
from pathlib import Path

from report import report


def write(path: Path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content))


def write_sample(turn: Path, sample: int, passed: bool | None):
    attempt = turn / 'ts' / str(sample) / 'attempts' / '0'
    if passed is None:
        write(attempt / 'generation.json', {'timed_out': True})
        return
    write(attempt / 'generation.json', {'exit_code': 0})
    write(attempt / 'tests.json', {'cases': [
        {'index': 0, 'stdout': '', 'stderr': '', 'passed': passed, 'status': 'ok'},
    ]})


async def test_timeout_exhausted_sample_completes_a_failed_turn(tmp_path):
    write(tmp_path / 'settings.json', {'t_samples': 2, 't_sample_retries': 0})
    write(tmp_path / 'result.json', {'success': True, 'attempts': 3})
    for window, samples in enumerate([[True, None], [True, True], [True, True]]):
        write(tmp_path / 'windows' / str(window) / 'window.json', {})
        write(tmp_path / 'windows' / str(window) / 'forks' / '0' / 'fork.json', {})
        turn = tmp_path / 'windows' / str(window) / 'forks' / '0' / 'turns' / '0'
        write(turn / 'metadata.json', {'advice': f'advices/{window}'})
        write(tmp_path / 'advices' / str(window) / 'advice.json', {'score': 10})
        (tmp_path / 'advices' / str(window) / 'advice.txt').write_text(f'advice {window}')
        for sample, passed in enumerate(samples):
            write_sample(turn, sample, passed)

    run, *attempts = await report(tmp_path)

    assert run['completed_evaluation_attempts'] == 3
    assert run['evaluation_attempts_to_success'] == 2
    assert attempts[0]['completed_evaluation_attempts'] == 1
    assert attempts[0]['outcome'] == 'failed_tests'
