import importlib
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from surprisals_experiment.config import Config
from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.utils.u_session import open_u_session
from surprisals_experiment.sdk.run_experiment.prepare_feedback import prepare_feedback

SNAPSHOTS = Path(__file__).with_name("snapshots")


@pytest.mark.parametrize("mode", ["chat", "agent"])
async def test_character_prompt_and_feedback_unchanged(config, mode, botbox_script):
    config.u_mode = mode
    async with open_u_session(config) as session:
        prompt = (session.messages[0]["content"] if mode == "chat" else
                  botbox_script.u_sessions[0].mounts["/u-config/u.txt"].read_text())
        assert prompt == (SNAPSHOTS / f"u-{mode}.txt").read_text()
    config.attempt_dir(0).mkdir(parents=True)
    snapshot = config.output / "snapshot"
    snapshot.mkdir()
    feedback = prepare_feedback(config, 0, [], snapshot=snapshot, advice_length=12,
                                best_length=None, turns_without_improvement=1)
    assert feedback == (SNAPSHOTS / f"feedback-{mode}.txt").read_text()


def test_surprisal_requires_endpoint(config):
    with pytest.raises(ValidationError, match="scorer_base_url"):
        Config(**(config.model_dump() | {"cap_strategy": "surprisal"}))


@pytest.mark.parametrize("mode", ["chat", "agent"])
async def test_bits_drive_improvement_feedback_and_result(config, botbox_script, monkeypatch, mode):
    module = importlib.import_module("surprisals_experiment.sdk.advice_measure")
    scorer = AsyncMock(side_effect=[10.5, 8.25, 8.25])
    monkeypatch.setattr(module, "measure_surprisal", scorer)
    config = Config(**(config.model_dump() | {
        "cap_strategy": "surprisal", "scorer_base_url": "http://scorer/v1", "u_mode": mode,
        "max_u_turns": 3, "max_turns_without_improvement": 1,
    }))
    botbox_script.advice.extend(["tiny", "much longer but fewer bits", "equal bits"])
    botbox_script.solutions.extend(["print(int(input())*2)"] * 3)
    solution = await run_experiment(config, on_delta=None)
    assert solution == config.t_dir(1, 0) / "src"
    assert scorer.await_count == 3
    client = scorer.call_args.kwargs["client"]
    assert client.model == config.t_model
    assert client.base_url == config.scorer_base_url
    assert json.loads(config.result_file.read_text())["best_measurement"] == 8.25
    assert json.loads(config.result_file.read_text())["cap_strategy"] == "surprisal"
    for attempt, bits in enumerate([10.5, 8.25, 8.25]):
        metadata = json.loads((config.advice_dir(attempt, 0) / "metadata.json").read_text())
        assert metadata["measurement"] == bits
        feedback = (config.attempt_dir(attempt) / "feedback.txt").read_text()
        assert f"Your advice was {bits} bits of surprisal." in feedback
        assert "characters" not in feedback
    assert "Turns without improvement: 0 of 1." in (config.attempt_dir(1) / "feedback.txt").read_text()
    assert "Turns without improvement: 1 of 1." in (config.attempt_dir(2) / "feedback.txt").read_text()


async def test_cli_cap_strategy_flags(config, monkeypatch):
    cli = importlib.import_module("surprisals_experiment.cli.main")
    run = AsyncMock()
    monkeypatch.setattr(cli, "run_experiment", run)
    monkeypatch.setattr(cli, "find_dotenv", lambda **kw: "unused")
    monkeypatch.setattr(cli, "dotenv_values", lambda *a, **kw: {"OPENROUTER_API_KEY": "test"})
    await cli.main(["--cap-strategy", "surprisal", "--scorer-base-url", "http://scorer/v1",
                    "--output", str(config.output), "problem", str(config.problem_dir)])
    received = run.call_args.args[0]
    assert received.cap_strategy == "surprisal"
    assert received.scorer_base_url == "http://scorer/v1"


async def test_surprisal_system_prompt_defines_the_measure(config):
    config = Config(**(config.model_dump() | {
        "cap_strategy": "surprisal", "scorer_base_url": "http://scorer/v1", "u_mode": "chat",
    }))
    async with open_u_session(config) as session:
        prompt = session.messages[0]["content"]
        assert "bits of surprisal under T's model" in prompt
        assert "Shorter means fewer bits." in prompt


async def test_failed_lower_bits_do_not_replace_success(config, botbox_script, monkeypatch):
    module = importlib.import_module("surprisals_experiment.sdk.advice_measure")
    monkeypatch.setattr(module, "measure_surprisal", AsyncMock(side_effect=[10.0, 1.0]))
    config = Config(**(config.model_dump() | {
        "cap_strategy": "surprisal", "scorer_base_url": "http://scorer/v1",
        "max_u_turns": 2, "max_turns_without_improvement": 1,
    }))
    botbox_script.advice.extend(["good", "bad"])
    botbox_script.solutions.extend(["print(int(input())*2)", "print(0)"])
    solution = await run_experiment(config, on_delta=None)
    assert solution == config.t_dir(0, 0) / "src"
    assert json.loads(config.result_file.read_text())["best_measurement"] == 10.0
