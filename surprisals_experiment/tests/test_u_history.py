"""U retains advice alongside every previous implementation."""

import json

from surprisals_experiment.sdk import run_experiment


async def test_all_previous_advice_and_sources_are_available(config, botbox_script, chat_provider):
    config.max_u_turns = 3
    config.t_samples = 2
    fail = 'print(0)\n'
    passed = 'print(int(input()) * 2)\n'
    botbox_script.advice.extend(['first', 'second', 'third'])
    botbox_script.solutions.extend([fail] * 4 + [passed] * 2)
    await run_experiment(config, on_delta=None)
    history = chat_provider[-1]['messages']
    sources = json.dumps({f'T {index}': {'main.py': fail} for index in range(2)}, indent=2)
    for attempt, advice in enumerate(['first', 'second']):
        assert history[2 * attempt + 2]['content'] == advice
        assert sources in history[2 * attempt + 3]['content']
