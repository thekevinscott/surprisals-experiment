"""Scorer rejection budgets are scoped to the current transcript attempt."""

import json

import httpx2
import pytest
from openai import BadRequestError
from run_database import ExperimentDatabase, QuestionDatabase

from surprisals_experiment.config import Config
from surprisals_experiment.retry_policy.constants import DELAYS
from surprisals_experiment.sdk.advice import Advice
from surprisals_experiment.sdk.run import Run
from surprisals_experiment.sdk.turn import Turn
from surprisals_experiment.sdk.utils.u_chat import open_u_chat
from surprisals_experiment.sdk.utils.write import write

from .score_advice import REJECTED, score_advice


@pytest.mark.parametrize('rejections', [len(DELAYS) - 1, len(DELAYS)])
async def test_later_turn_rejection_cap(config, scorer_provider, rejections):
    config = Config(**(config.model_dump() | {
        'cap_strategy': 'surprisal', 'scorer_base_url': 'http://scorer/v1',
    }))
    turn = Turn(config, 1)
    advice = Advice(config.output, 'too long', config.advice_measure)
    metadata = turn.attempt_dir / 'metadata.json'
    write(metadata, json.dumps({'advice': advice.id}) + '\n')
    rejection = {'role': 'user', 'content': REJECTED}
    entries = []
    for attempt, count in ((0, len(DELAYS)), (1, rejections)):
        entries.append({'role': 'user', 'content': 'feedback', '_attempt': attempt})
        for _ in range(count):
            entries.extend([{'role': 'assistant', 'content': 'too long'}, rejection])
    entries.append({'role': 'assistant', 'content': 'too long'})
    before = ''.join(json.dumps(entry, ensure_ascii=False) + '\n' for entry in entries).encode()
    transcript = config.fork_dir / 'u/transcript.jsonl'
    write(transcript, before)
    scorer_provider.replies.append(httpx2.Response(
        400, json={'error': {'message': 'maximum context length is 8192 tokens'}},
    ))
    async with open_u_chat(config, transcript=transcript) as chat:
        run = Run(config, ExperimentDatabase(config.output), QuestionDatabase(config.problem_dir), {}, u_chat=chat)
        if rejections == len(DELAYS):
            with pytest.raises(BadRequestError, match='context limit'):
                await score_advice(run, turn)
            assert chat.transcript.read_bytes() == before
            assert metadata.exists()
        else:
            await score_advice(run, turn)
            appended = (json.dumps(rejection, ensure_ascii=False) + '\n').encode()
            assert chat.transcript.read_bytes() == before + appended
            assert not metadata.exists()
    assert len(scorer_provider.requests) == 1
