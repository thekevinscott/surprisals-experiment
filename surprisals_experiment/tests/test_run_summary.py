"""Exercise the SQL report against artifacts from the real experiment loops."""

import json
from pathlib import Path
import subprocess

import pytest

from surprisals_experiment.sdk import run_experiment

SQL = (Path(__file__).resolve().parents[2] / 'scripts/run-summary.sql').read_text()
PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'


def report(folder):
    result = subprocess.run(['dirsql', '--no-ignore', '--format', 'json', '--', SQL],
                            cwd=folder, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def describe_run_summary():
    @pytest.mark.parametrize('failures', [0, 2, 5])
    async def it_counts_rewrites_separately_from_evaluations(config, botbox_script, failures):
        config.u_advice_max_chars = 5
        count = min(failures + 1, 5)
        config.max_u_turns = count
        botbox_script.advice.extend(['12345', 'ok'] * count)
        botbox_script.solutions.extend([FAIL] * failures + [PASS])
        await run_experiment(config, on_delta=None)
        (config.output / 'run.json').write_text(json.dumps({
            'params': {'u-advice-max-chars': 5},
        }))
        summary, *attempts = report(config.output)
        assert summary['cap'] == 5
        assert summary['cap_status'] == 'recorded'
        assert summary['advice_candidates'] == count * 2
        assert summary['advice_rewrites'] == count
        assert summary['rejected_candidates'] == count
        assert summary['completed_t_evaluations'] == count
        assert summary['passing_ts'] == (1 if failures < 5 else 0)
        assert summary['evaluation_attempts_to_success'] == (count if failures < 5 else None)
        assert [row['attempt_index'] for row in attempts] == list(range(count))
        assert all(row['advice_rewrites'] == 1 for row in attempts)
        assert all(row['accepted_characters'] == 2 for row in attempts)
        assert [row['tests_passed'] for row in attempts] == [0] * failures + ([2] if failures < 5 else [])

    @pytest.mark.parametrize('failure', ['rewrite_exhaustion', 't_infrastructure'])
    async def it_does_not_count_missing_evaluations_as_failed_ts(config, botbox_script, failure):
        config.u_advice_max_chars = 5
        config.u_advice_retries = 2
        botbox_script.advice.extend(['12345'] * 3 if failure == 'rewrite_exhaustion' else ['ok'])
        botbox_script.solutions.append(RuntimeError('provider unavailable'))
        with pytest.raises(RuntimeError):
            await run_experiment(config, on_delta=None)
        summary, attempt = report(config.output)
        assert summary['completed_t_evaluations'] == 0
        assert summary['evaluation_attempts_to_success'] is None
        assert summary['outcome'] == 'no_final_result'
        assert summary['cap_status'] == 'recorded'
        assert summary['advice_rewrites'] == (2 if failure == 'rewrite_exhaustion' else 0)
        assert attempt['outcome'] == 'not_evaluated'
        assert attempt['passing_ts'] is None

    def it_handles_a_run_without_saved_advice(config):
        config.output.mkdir()
        summary, = report(config.output)
        assert summary['completed_t_evaluations'] == 0
        assert summary['advice_candidates'] is None
        assert summary['cap_status'] == 'unknown'
        assert summary['outcome'] == 'no_final_result'
