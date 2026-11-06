"""Real preflight and evaluator behavior, with only model and Botbox calls mocked."""
import json

from run_one_window import run_one_window
from u_flush_test import PASS, QUESTION, flush, outcome, played

TURN = 'windows/0/forks/0/turns/0'


async def test_nonzero_t_exit_can_produce_valid_solution_and_duration(config, execute_run_experiment):
    attempt = f'{TURN}/ts/0/attempts/0'
    states, pending = played([[(QUESTION, 'Double it.', [PASS])], [(flush(0, 'Double it.', length=10), 'Double it.', [PASS])]],
                             {'Double it.': {'score': 10}})
    states[1].reply.exit_code = 1
    states[2].files[f'{attempt}/generation.json'] = {'exit_code': 1}
    async with execute_run_experiment(config, [*states, outcome(config, TURN, 2, pending)]):
        pass


async def test_case_exceeding_five_seconds_fails(config, botbox_script):
    (config.problem_dir / 'input_output.json').write_text(json.dumps({'inputs': [''], 'outputs': ['done']}))
    botbox_script.advice.append('Print done.')
    botbox_script.solutions.append('import time; time.sleep(6); print("done")')
    assert await run_one_window(config, on_delta=None) is None
    result = json.loads((config.t_dir(0, 0) / 'attempts/0/tests.json').read_text())
    assert result['passed'] == 0
    assert result['cases'][0]['stderr'] == 'Test exceeded 5 seconds'
    assert result['duration_seconds'] >= 5
