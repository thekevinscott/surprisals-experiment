"""What a run leaves in result.json and its folder."""

import json

from measure_test import scoring_config
from u_flush_test import QUESTION, Containing, flush, outcome, played
from state_machine.testing import Done, State

from utils.world import T, t_sent

PASS = 'print(int(input()) * 2)\n'
FAIL = 'print(0)\n'
TURN = 'windows/0/forks/0/turns/0'


def read(config, pattern):
    return {path.relative_to(config.output).as_posix(): json.loads(path.read_text())
            for path in config.output.glob(pattern)}


def evaluations(config):
    return read(config, 'windows/*/forks/*/turns/*/ts/*/attempts/*/tests.json')


def result(config):
    return json.loads((config.output / 'result.json').read_text())


def describe_run_result():
    async def it_counts_one_advice_per_evaluation(config, execute_run_experiment):
        config.max_u_turns = 3
        best = flush(2, 'ok', length=2)
        states, pending = played([[(QUESTION, 'ok', [FAIL])] * 2 + [(QUESTION, 'ok', [PASS])],
                                  [(best, 'ok', [PASS])] * 3], {'ok': {'score': 2}}, config=config)
        async with execute_run_experiment(config, [*states, outcome(config, 'windows/0/forks/0/turns/2', 6, pending)]):
            pass
        assert result(config)['attempts'] == 6
        assert result(config)['solution'] == str(config.output / 'windows/0/forks/0/turns/2/ts/0/attempts/0/src')
        assert sorted(tests['passed'] for tests in evaluations(config).values()) == [0, 0, 2, 2, 2, 2]
        advices = {metadata['advice'] for metadata in read(config, 'windows/*/forks/*/turns/*/metadata.json').values()}
        assert [json.loads((config.output / advice / 'advice.json').read_text()) for advice in advices] == [{'score': 2}]

    async def it_does_not_count_missing_evaluations_as_failed_ts(config, execute_run_experiment):
        [asked], pending = played([[(QUESTION, 'ok', [])]], {'ok': {'score': 2}}, config=config)
        error = RuntimeError('provider unavailable')
        retries = [[]] + [[(f'{TURN}/ts/0', 'retry', f'T {attempt}/8 in {wait}s: provider unavailable\n')]
                          for attempt, wait in enumerate([10, 20, 30, 60, 180, 300, 1200, 1800], 1)]
        failure = 'T sample failed: provider unavailable; 8 retries exhausted'
        world = [
            asked,
            *[State(T(error=error), sent=t_sent(f'{TURN}/ts/0/attempts/{attempt}', 'ok'), logs=retries[attempt],
                    files=None if attempt else pending) for attempt in range(9)],
            Done(outcome=RuntimeError(failure), files={f'{TURN}/error.txt': Containing(failure)}),
        ]
        async with execute_run_experiment(config, world):
            pass
        assert not (config.output / 'result.json').exists()
        assert evaluations(config) == {}
        assert (config.output / TURN / 'error.txt').exists()

    async def it_reads_shared_advice_scores(scoring_config, execute_run_experiment):
        config = scoring_config
        advice = 'Use café.'
        best = flush(0, advice, bits=f'{advice}<3.2>')
        states, pending = played([[(QUESTION, advice, [PASS])], [(best, advice, [PASS])]],
                                 {advice: {'score': 3.25, 'tokens': [[advice, 3.25]]}},
                                 bits={advice: [(advice, 3.25)]}, config=config)
        async with execute_run_experiment(config, [*states, outcome(
                config, TURN, 2, pending, best_measurement=3.25, cap_strategy='surprisal',
                scorer_base_url='http://scorer/v1', scorer_model='t')]):
            pass
        assert len(list((config.output / 'advices').iterdir())) == 1
        assert result(config)['best_measurement'] == 3.25
