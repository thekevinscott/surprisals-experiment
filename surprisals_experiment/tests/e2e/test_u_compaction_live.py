"""Compact a real chat U conversation through OpenRouter. Costs a few U calls."""

import asyncio
import json

import pytest
from dotenv import dotenv_values, find_dotenv

from surprisals_experiment.config import Config, U_MODEL, T_MODEL
from surprisals_experiment.sdk.utils.u_chat import open_u_session
from surprisals_experiment.sdk.utils.u_chat.history import build_messages
from surprisals_experiment.sdk.utils.u_chat.compact import preamble

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
            messages = build_messages(live_config, 0)
            first_reply = await session.prompt(messages)
            first = first_reply['content']
            state = dict(best_advice=first, best_length=len(first), turns_without_improvement=3)
            summary_file = live_config.attempt_dir(1) / 'summary.txt'
            await session.compact([*messages, first_reply], summary_file, question=QUESTION, **state)
            feedback = 'All T samples passed. Try shorter advice.'
            second = await session.prompt([
                messages[0],
                {'role': 'user', 'content': preamble(QUESTION, summary_file.read_text(), **state)},
                {'role': 'user', 'content': feedback},
            ])

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
        assert second['content'].strip()
