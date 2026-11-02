"""Compact a real chat U conversation through OpenRouter. Costs a few U calls."""

import asyncio
import json

import pytest
from dotenv import dotenv_values, find_dotenv

from surprisals_experiment.config import Config, U_MODEL, T_MODEL
from surprisals_experiment.sdk.utils.u_session import open_u_session

QUESTION = 'Read an integer n from standard input and print 2 * n.'


@pytest.fixture
def live_config(tmp_path):
    key = dotenv_values(find_dotenv(usecwd=True)).get('OPENROUTER_API_KEY')
    if not key:
        pytest.skip('needs OPENROUTER_API_KEY in .env')
    problem = tmp_path / 'problem'
    problem.mkdir()
    (problem / 'question.txt').write_text(QUESTION)
    return Config(
        api_key=key, problem_dir=problem, output=tmp_path / 'run',
        u_model=U_MODEL, t_model=T_MODEL, u_thinking='low', t_samples=1,
    )


def describe_live_chat_compaction():
    async def it_summarizes_then_keeps_advising_from_the_measured_state(live_config):
        async with asyncio.timeout(600), open_u_session(live_config) as session:
            first = await session.prompt(QUESTION)
            session.best_advice, session.best_length, session.turns_without_improvement = first, len(first), 3
            session.compact_chars = 1
            feedback = 'All T samples passed. Try shorter advice.'
            second = await session.prompt(feedback)

        transcript = [json.loads(line) for line in live_config.u_transcripts.joinpath('messages.jsonl').read_text().splitlines()]
        roles = [m['role'] for m in transcript]
        assert roles == ['system', 'user', 'assistant', 'user', 'assistant', 'user', 'user', 'assistant']
        summary = transcript[4]['content']
        assert summary and 'summary unavailable' not in summary
        assert summary.strip() != first.strip()
        preamble = transcript[5]['content']
        assert f'<prior_summary>\n{summary}\n</prior_summary>' in preamble
        assert f'<best_successful_advice>\n{first}\n</best_successful_advice>' in preamble
        assert f'Best successful advice length: {len(first)}' in preamble
        assert 'Turns without improvement: 3' in preamble
        assert QUESTION in preamble
        assert transcript[6]['content'] == feedback
        assert [m['role'] for m in session.messages] == ['system', 'user', 'user', 'assistant']
        assert second.strip()
