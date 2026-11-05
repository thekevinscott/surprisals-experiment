"""CLI options reach the real experiment, with providers replaced at the boundary."""

import json

import pytest
from pydantic import ValidationError

from surprisals_experiment.cli.main import main
from surprisals_experiment.config import Config


async def test_cli_runs_with_selected_measure_and_stopping_budget(config, botbox_script, scorer_provider, chat_provider, monkeypatch):
    (config.problem_dir / '.env').write_text('OPENROUTER_API_KEY=test-key\n')
    monkeypatch.chdir(config.problem_dir)
    scorer_provider.replies.append([('Double.', 7.0)])
    botbox_script.advice.extend(['Double.'] * 2)
    botbox_script.solutions.extend(['print(int(input()) * 2)'] * 4)
    await main(['--window-forks', '1',
        '-U', 'selected-u', '-T', 'selected-t', '--cap-strategy', 'surprisal',
        '--scorer-base-url', 'http://scorer/v1', '--max-u-turns', '1',
        '--t-samples', '2', '--t-pool-size', '1', '--output', str(config.output),
        'problem', str(config.problem_dir),
    ])
    result = json.loads(config.result_file.read_text())
    assert result['success'] and result['attempts'] == 2
    assert result['cap_strategy'] == 'surprisal'
    assert result['best_measurement'] == pytest.approx(7.0)
    assert len(botbox_script.sessions) == 4
    assert all(request['model'] == 'selected-u' for request in chat_provider)
    assert scorer_provider.requests[0]['model'] == 'selected-t'


def test_rejects_nonpositive_stopping_budget(config):
    with pytest.raises(ValidationError, match='max_u_turns'):
        Config(**(config.model_dump() | {'max_u_turns': 0}))


def test_surprisal_requires_endpoint(config):
    with pytest.raises(ValidationError, match='scorer_base_url'):
        Config(**(config.model_dump() | {'cap_strategy': 'surprisal'}))
