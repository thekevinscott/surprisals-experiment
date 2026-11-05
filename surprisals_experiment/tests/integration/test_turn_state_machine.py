"""A turn resumes after persisted advice without asking U again."""

import asyncio
import json
from unittest.mock import patch

import pytest

from run_one_window import run_one_window
from surprisals_experiment.sdk.run_experiment.run_experiment import actions


async def test_interrupted_after_advice_resumes_at_scoring(config, botbox_script, chat_provider):
    config.max_u_turns = 1
    botbox_script.advice.append('Double.')
    botbox_script.solutions.append('print(int(input()) * 2)\n')

    async def interrupt(*args, **kwargs):
        raise asyncio.CancelledError

    with patch.dict(actions, {"unscored": interrupt}):
        with pytest.raises(asyncio.CancelledError):
            await run_one_window(config, on_delta=None)
    assert (config.attempt_dir(0) / 'metadata.json').exists()
    assert len(chat_provider) == 1
    assert not botbox_script.sessions

    solution = await run_one_window(config, on_delta=None)
    assert len(chat_provider) == 1
    assert solution == config.t_dir(0, 0) / 'src'
    assert json.loads((config.t_dir(0, 0) / 'tests.json').read_text())['all_passed']
    assert (config.attempt_dir(0) / 'feedback.txt').exists()
    assert json.loads(config.result_file.read_text())['success']
