"""Scorer rejection feedback stays in the next request to U."""

from measure_test import (
    OVERFLOW,
    QUESTION,
    opened,
    rejected,
    score_state,
    turn,
    u_state,
    unscored,
)
from u_flush_test import Containing, chat
from utils.world import u_system

from surprisals_experiment.config import Config


async def test_scorer_rejection_is_appended_to_u_context(config, execute_run_experiment):
    config = Config(**(config.model_dump() | {'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1'}))
    path = turn(0, 0)
    first = u_state(config, path, QUESTION, 'too long 0', {'settings.json': ..., **opened(0), **chat(0, (QUESTION, None))})
    first.sent['messages'] = [{'role': 'system', 'content': u_system(config, 1)}, {'role': 'user', 'content': QUESTION}]
    retry = u_state(config, path, QUESTION, 'shorter', {
        **rejected(path, 0), 'u/transcripts/messages.jsonl': ...,
    })
    retry.sent['messages'] = [
        *first.sent['messages'],
        {'role': 'assistant', 'content': 'too long 0'},
        {'role': 'user', 'content': Containing(OVERFLOW)},
    ]
    world = [
        first,
        score_state('too long 0', {**unscored(path, 'too long 0'), **chat(0, (QUESTION, 'too long 0'))},
                    status=400, message=OVERFLOW),
        retry,
    ]
    async with execute_run_experiment(config, world, u_layout=True) as run:
        await run.reached(retry)
        run.kill()
