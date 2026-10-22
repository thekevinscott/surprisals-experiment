"""U retains advice alongside every previous implementation."""

from surprisals_experiment.sdk import run_experiment


async def test_all_previous_advice_and_sources_are_available(config, botbox_script):
    config.max_u_turns = 3
    config.t_samples = 2
    fail = 'print(0)\n'
    passed = 'print(int(input()) * 2)\n'
    botbox_script.advice.extend(['first', 'second', 'third'])
    botbox_script.solutions.extend([fail] * 4 + [passed] * 2)
    await run_experiment(config, on_delta=None)
    history = botbox_script.snapshots[-1]
    for attempt, advice in enumerate(['first', 'second']):
        assert history[f'{attempt}/advice.txt'] == advice
        for sample in range(2):
            assert history[f'{attempt}/{sample}/main.py'] == fail
