"""A fork resumes its unfinished turn without repeating completed turns."""

import asyncio
import json
from unittest.mock import patch

import pytest

from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.run_experiment.run_experiment import actions


async def test_interrupted_second_turn_resumes_without_repeating_first(config, botbox_script, chat_provider):
    config.max_u_turns = 2
    botbox_script.advice.extend(['Double it.', 'Double.'])
    botbox_script.solutions.extend(['print(int(input()) * 2)\n'] * 2)
    score = actions["unscored"]

    async def interrupt(run, turn):
        if turn.position == 1:
            raise asyncio.CancelledError
        await score(run, turn)

    with patch.dict(actions, {"unscored": interrupt}):
        with pytest.raises(asyncio.CancelledError):
            await run_experiment(config, on_delta=None)
    first = config.t_dir(0, 0) / 'generation.json'
    before = (first.read_bytes(), first.stat().st_mtime_ns)
    assert (config.attempt_dir(0) / 'feedback.txt').exists()
    assert (config.attempt_dir(1) / 'metadata.json').exists()
    assert len(chat_provider) == 2
    assert len(botbox_script.sessions) == 1

    solution = await run_experiment(config, on_delta=None)
    assert solution == config.t_dir(1, 0) / 'src'
    assert len(chat_provider) == 2
    assert len(botbox_script.sessions) == 2
    assert (first.read_bytes(), first.stat().st_mtime_ns) == before
    assert (config.attempt_dir(1) / 'feedback.txt').exists()
    assert json.loads(config.result_file.read_text())['attempts'] == 2
