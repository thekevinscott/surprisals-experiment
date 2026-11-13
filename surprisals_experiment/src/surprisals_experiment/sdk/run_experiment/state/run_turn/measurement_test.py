"""Resume fills a missing measurement once without another provider call."""

import json

import pytest
from run_database import ExperimentDatabase, QuestionDatabase
from surprisals_experiment.config import Config
from surprisals_experiment.sdk.advice import Advice
from surprisals_experiment.sdk.run import Run
from surprisals_experiment.sdk.turn import Turn
from surprisals_experiment.sdk.utils.append import append
from surprisals_experiment.sdk.utils.u_chat import open_u_chat
from surprisals_experiment.sdk.utils.write import write
from surprisals_experiment.sdk.run_experiment.actions.score_advice import score_advice
from .machine import state


@pytest.mark.parametrize('measure', ['characters', 'surprisal'])
async def test_resume_after_score_appends_measurement_exactly_once(config, chat_provider, measure):
    config = Config(**(config.model_dump() | {
        'cap_strategy': measure, 'scorer_base_url': 'http://scorer/v1',
    }))
    turn = Turn(config, 0)
    write(config.window_dir / 'window.json', '{}')
    write(config.fork_dir / 'fork.json', '{}')
    advice = Advice(config.output, 'Double.', config.advice_measure)
    advice.metadata = {'score': 7} if measure == 'characters' else {'score': 3.25, 'tokens': [['Double.', 3.25]]}
    advice.save()
    write(turn.attempt_dir / 'metadata.json', json.dumps({'advice': advice.id}))
    async with open_u_chat(config, transcript=config.fork_dir / 'u/transcript.jsonl') as chat:
        append(chat.transcript, json.dumps({'role': 'user', 'content': 'turn 1 of 20', '_attempt': 0}) + '\n')
        append(chat.transcript, json.dumps({'role': 'assistant', 'content': advice.text}) + '\n')
    async with open_u_chat(config, transcript=config.fork_dir / 'u/transcript.jsonl') as chat:
        run = Run(config, ExperimentDatabase(config.output), QuestionDatabase(config.problem_dir), {}, u_chat=chat)
        assert await state(run, turn) == 'unscored'
        await score_advice(run, turn)
        saved = chat.transcript.read_bytes()
        assert chat.entries()[-1] == {'role': 'user', 'content': advice.measurement}
        assert await state(run, turn) == 'solutions_missing'
        await score_advice(run, turn)
        assert chat.transcript.read_bytes() == saved
    assert chat_provider == []
