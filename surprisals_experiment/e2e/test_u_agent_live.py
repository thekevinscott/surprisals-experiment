"""Exercise agent U's real provider route through the credential proxy."""

import asyncio

import pytest
from dotenv import dotenv_values, find_dotenv

from surprisals_experiment.config import Config, U_MODEL, T_MODEL
from surprisals_experiment.sdk.utils.u_session import open_u_session

QUESTION = 'Read an integer n and print 2 * n. Give one short sentence of advice.'


@pytest.fixture
def live_agent_config(tmp_path):
    key = dotenv_values(find_dotenv(usecwd=True)).get('OPENROUTER_API_KEY')
    if not key:
        pytest.skip('needs OPENROUTER_API_KEY in .env')
    problem = tmp_path / 'problem'
    problem.mkdir()
    (problem / 'question.txt').write_text(QUESTION)
    return Config(
        api_key=key, problem_dir=problem, output=tmp_path / 'run', u_mode='agent',
        u_model=U_MODEL, t_model=T_MODEL, u_thinking='off', t_samples=1,
        max_u_turns=1,
    )


async def test_agent_u_returns_advice(live_agent_config):
    async with asyncio.timeout(180), open_u_session(live_agent_config) as session:
        advice = await session.prompt(QUESTION)
    assert advice.strip()
