"""Real preflight and evaluator behavior, with only model and Botbox calls mocked."""
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
