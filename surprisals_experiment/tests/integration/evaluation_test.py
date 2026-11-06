"""Real preflight and evaluator behavior, with only model and Botbox calls mocked."""
from u_flush_test import PASS, QUESTION, flush, outcome, played

TURN = 'windows/0/forks/0/turns/0'


async def test_nonzero_t_exit_can_produce_valid_solution_and_duration(config, execute_run_experiment):
    attempt = f'{TURN}/ts/0/attempts/0'
    states, pending = played([[(QUESTION, 'Double it.', [PASS])], [(flush(0, 'Double it.', length=10), 'Double it.', [PASS])]],
                             {'Double it.': {'score': 10}}, config=config)
    states[1].reply.exit_code = 1
    states[2].files[f'{attempt}/generation.json'] = {'exit_code': 1}
    async with execute_run_experiment(config, [*states, outcome(config, TURN, 2, pending)]):
        pass


async def test_test_cases_cannot_write_into_the_run_folder(config, execute_run_experiment):
    tamper = ("from pathlib import Path\nPath('../tampered.txt').write_text('x')\nPath('stray.txt').write_text('x')\n"
              "print(int(input()) * 2)\n")
    states, pending = played([[(QUESTION, 'Double it.', [tamper])],
                              [(flush(0, 'Double it.', length=10, codes=[tamper]), 'Double it.', [tamper])]],
                             {'Double it.': {'score': 10}}, config=config)
    async with execute_run_experiment(config, [*states, outcome(config, TURN, 2, pending)]):
        pass
