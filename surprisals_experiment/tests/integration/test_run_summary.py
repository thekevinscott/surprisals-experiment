"""Exercise the SQL report against artifacts from the real experiment loops."""

import json
from pathlib import Path
import subprocess

from advice_artifacts import write_advice
from test_u_flush import QUESTION, Containing, flush, outcome, played
from utils.world import Done, State, T

SQL = (Path(__file__).resolve().parents[3] / 'scripts/run-summary.sql').read_text()
PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'
TURN = 'windows/0/forks/0/turns/0'


def report(folder):
    result = subprocess.run(['dirsql', '--no-ignore', '--format', 'json', '--', SQL],
                            cwd=folder, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def describe_run_summary():
    async def it_counts_one_advice_per_evaluation(config, execute_run_experiment):
        config.max_u_turns = 3
        best = flush(2, 'ok', length=2)
        states, pending = played([[(QUESTION, 'ok', [FAIL])] * 2 + [(QUESTION, 'ok', [PASS])],
                                  [(best, 'ok', [PASS])] * 3], {'ok': {'score': 2}})
        async with execute_run_experiment(config, [*states, outcome(config, 'windows/0/forks/0/turns/2', 6, pending)]):
            pass
        summary, *attempts = report(config.output)
        assert summary['cap'] is None
        assert summary['cap_status'] == 'uncapped'
        assert summary['completed_t_evaluations'] == 6
        assert summary['passing_ts'] == 4
        assert summary['evaluation_attempts_to_success'] == 3
        assert [row['attempt_index'] for row in attempts] == [0, 0, 1, 1, 2, 2]
        assert all(row['score'] == 2 for row in attempts)
        assert sorted(row['tests_passed'] for row in attempts) == [0, 0, 2, 2, 2, 2]

    async def it_does_not_count_missing_evaluations_as_failed_ts(config, execute_run_experiment):
        [asked], pending = played([[(QUESTION, 'ok', [])]], {'ok': {'score': 2}})
        error = RuntimeError('provider unavailable')
        retries = [[]] + [[(f'{TURN}/ts/0', 'retry', f'T {attempt}/8 in {wait}s: provider unavailable\n')]
                          for attempt, wait in enumerate([10, 20, 30, 60, 180, 300, 1200, 1800], 1)]
        failure = 'T sample failed: provider unavailable; 8 retries exhausted'
        world = [
            asked,
            *[State(T(error=error), sent=(f'{TURN}/ts/0/attempts/{attempt}', 'ok'), logs=retries[attempt],
                    files=None if attempt else pending) for attempt in range(9)],
            Done(outcome=RuntimeError(failure), files={f'{TURN}/error.txt': Containing(failure)}),
        ]
        async with execute_run_experiment(config, world):
            pass
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
