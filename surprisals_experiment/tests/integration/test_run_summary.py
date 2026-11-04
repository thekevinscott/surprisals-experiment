"""Exercise the SQL report against artifacts from the real experiment loops."""

import json
from pathlib import Path
import subprocess

import pytest

from fork_runner import run_fork as run_experiment
from advice_artifacts import write_advice

SQL = (Path(__file__).resolve().parents[3] / 'scripts/run-summary.sql').read_text()
PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'


def report(folder):
    result = subprocess.run(['dirsql', '--no-ignore', '--format', 'json', '--', SQL],
                            cwd=folder, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def describe_run_summary():
    async def it_counts_one_advice_per_evaluation(config, botbox_script):
        failures = 2
        count = min(failures + 1, 5)
        config.max_u_turns = count
        botbox_script.advice.extend(['ok'] * count)
        botbox_script.solutions.extend([FAIL] * failures + [PASS])
        await run_experiment(config, on_delta=None)
        summary, *attempts = report(config.output)
        assert summary['cap'] is None
        assert summary['cap_status'] == 'uncapped'
        assert summary['completed_t_evaluations'] == count
        assert summary['passing_ts'] == (1 if failures < 5 else 0)
        assert summary['evaluation_attempts_to_success'] == (count if failures < 5 else None)
        assert [row['attempt_index'] for row in attempts] == list(range(count))
        assert all(row['score'] == 2 for row in attempts)
        assert [row['tests_passed'] for row in attempts] == [0] * failures + ([2] if failures < 5 else [])

    async def it_does_not_count_missing_evaluations_as_failed_ts(config, botbox_script, no_retry_wait):
        botbox_script.advice.append('ok')
        botbox_script.solutions.extend([RuntimeError('provider unavailable')] * 9)
        with pytest.raises(RuntimeError):
            await run_experiment(config, on_delta=None)
        summary, attempt = report(config.output)
        assert summary['completed_t_evaluations'] == 0
        assert summary['evaluation_attempts_to_success'] is None
        assert summary['outcome'] == 'no_final_result'
        assert summary['cap_status'] == 'uncapped'
        assert attempt['outcome'] == 'not_evaluated'
        assert attempt['passing_ts'] is None

    def it_handles_a_run_without_saved_advice(config):
        config.output.mkdir()
        summary, = report(config.output)
        assert summary['completed_t_evaluations'] == 0
        assert summary['cap_status'] == 'unknown'
        assert summary['outcome'] == 'no_final_result'

    def it_reads_shared_advice_scores(config):
        turn = config.attempt_dir(0)
        turn.mkdir(parents=True)
        write_advice(config, turn, 'Use café.\r\n', 3.25, tokens=[{'text': 'Use', 'surprisal': 3.25}])
        summary, attempt = report(config.output)
        assert attempt['score'] == 3.25
