"""A window completes its fork and does not ask U again once finished."""

import json
from unittest.mock import patch

from surprisals_experiment.sdk import run_experiment


async def test_finished_window_rerun_does_not_ask_u(config, botbox_script, chat_provider):
    botbox_script.advice.append('Double it.')
    botbox_script.solutions.append('print(int(input()) * 2)\n')

    solution = await run_experiment(config, on_delta=None)
    assert solution == config.t_dir(0, 0) / 'src'
    assert json.loads(config.result_file.read_text())['success']
    assert len(chat_provider) == 1
    assert len(botbox_script.sessions) == 1

    with patch('surprisals_experiment.sdk.utils.u_chat.ChatSession.prompt',
               side_effect=AssertionError('Finished window asked U again')) as prompt:
        assert await run_experiment(config, on_delta=None) == solution
        prompt.assert_not_awaited()
    assert len(chat_provider) == 1
    assert len(botbox_script.sessions) == 1
