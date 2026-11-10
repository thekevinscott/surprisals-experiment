"""CLI options reach the real experiment, with providers replaced at the boundary."""

import json
import os
from contextlib import chdir
from unittest.mock import patch

import pytest
from state_machine.testing import Done
from surprisals_experiment.cli.main import main
from surprisals_experiment.config import T_MODEL, U_MODEL
from utils.world import T, U, t_sent

from u_flush_test import PASS, QUESTION, flush, played


@pytest.fixture
def in_problem_dir(config):
    with chdir(config.problem_dir):
        yield


@pytest.fixture
def labnotes_log(config):
    log = config.problem_dir / "log.jsonl"
    with patch.dict(os.environ, {"LABNOTES_LOG": str(log)}):
        yield log


@pytest.fixture
def labnotes_run_state(tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"base_url": "http://state-scorer/v1"}))
    with patch.dict(os.environ, {"LABNOTES_RUN_STATE": str(state)}):
        yield


def world(config, u_model, t_model, url, u_provider='xiaomi', scorer_model='openai/gpt-oss-120b'):
    """Two windows of one turn, two T samples each, run one at a time; the run's own logs go to labnotes."""
    best = flush(0, 'Double.', bits='Double.<7.0>', codes=(PASS, PASS))
    states, pending = played([[(QUESTION, 'Double.', [PASS, PASS])], [(best, 'Double.', [PASS, PASS])]],
                             {'Double.': {'score': 7.0, 'tokens': [['Double.', 7.0]]}}, sequential=True,
                             bits={'Double.': [('Double.', 7.0)]}, config=config.model_copy(update={
                                 'cap_strategy': 'surprisal', 'scorer_base_url': url, 't_samples': 2}))
    for state in states:
        state.logs = []
        if isinstance(state.reply, U):
            state.sent['model'] = u_model
            state.sent['provider'] = {'only': [u_provider], 'allow_fallbacks': False}
        if isinstance(state.reply, T):
            state.sent = t_sent(state.sent['output'], 'Double.', model=t_model)
    solution = config.output / 'windows/0/forks/0/turns/0/ts/0/attempts/0/src'
    return [*states, Done(outcome=None, files={**pending, 'result.json': {
        'success': True, 'attempts': 2, 'solution': str(solution), 'best_measurement': 7.0,
        'cap_strategy': 'surprisal', 'scorer_base_url': url, 'scorer_model': scorer_model}})]


async def test_cli_runs_with_selected_measure_and_stopping_budget(
    config, labnotes_log, in_problem_dir, execute_run_experiment
):
    (config.problem_dir / ".env").write_text("OPENROUTER_API_KEY=test-key\n")
    settings = {'window_solo_turns': 2, 'u_model': 'selected-u', 'u_provider': 'selected-provider', 't_model': 'selected-t',
                't_provider': 'selected-t-provider', 'scorer_model': 'selected-scorer'}
    argv = [
        "--window-forks", "1", "--window-solo-turns", "2", "-U", "selected-u", "--u-provider", "selected-provider",
        "-T", "selected-t", "--t-provider", "selected-t-provider", "--scorer-model", "selected-scorer",
        "--cap-strategy", "surprisal", "--scorer-base-url", "http://scorer/v1", "--max-u-turns", "1",
        "--t-samples", "2", "--t-pool-size", "1", "--output", str(config.output), str(config.problem_dir),
    ]
    async with execute_run_experiment(config, world(config, 'selected-u', 'selected-t', 'http://scorer/v1', 'selected-provider', 'selected-scorer'), run=main(argv)):
        pass
    written = json.loads((config.output / "settings.json").read_text())
    assert written.items() >= settings.items()
    assert "window_turns" not in written
    blocks = [json.loads(line) for line in labnotes_log.read_text().splitlines()]
    starts = {block["id"]: block for block in blocks if block.get("phase") == "start"}
    stops = {block["id"] for block in blocks if block.get("phase") == "stop"}
    assert starts.keys() == stops
    streams = {block_id.rsplit("/", 1)[0] for block_id in starts}
    assert len([stream for stream in streams if stream.endswith("/u")]) == 2
    assert len([stream for stream in streams if "/ts/" in stream]) == 4
    assert {"thinking", "text"} <= {block["type"] for block in starts.values()}


async def test_surprisal_reads_scorer_url_from_labnotes_state(
    config, labnotes_run_state, in_problem_dir, execute_run_experiment
):
    (config.problem_dir / ".env").write_text("OPENROUTER_API_KEY=test-key\n")
    argv = [
        "--window-forks", "1", "--window-solo-turns", "2", "--cap-strategy", "surprisal", "--max-u-turns", "1",
        "--t-samples", "2", "--t-pool-size", "1", "--output", str(config.output), str(config.problem_dir),
    ]
    async with execute_run_experiment(config, world(config, U_MODEL, T_MODEL, 'http://state-scorer/v1'), run=main(argv)):
        pass
    assert json.loads((config.output / "settings.json").read_text())["scorer_base_url"] == "http://state-scorer/v1"
