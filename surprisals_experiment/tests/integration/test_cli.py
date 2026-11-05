"""CLI options reach the real experiment, with providers replaced at the boundary."""

import json

import pytest
from conftest import FakeSession
from pydantic import ValidationError
from surprisals_experiment.cli.main import main
from surprisals_experiment.config import Config


async def test_cli_runs_with_selected_measure_and_stopping_budget(
    config, botbox_script, scorer_provider, chat_provider, monkeypatch
):
    original_message = FakeSession.message

    async def message(self, text):
        self.agent.receive(
            {
                "type": "message_update",
                "assistantMessageEvent": {
                    "type": "text_delta",
                    "delta": "Writing solution.",
                },
            }
        )
        await original_message(self, text)

    monkeypatch.setattr(FakeSession, "message", message)
    log = config.problem_dir / "log.jsonl"
    monkeypatch.setenv("LABNOTES_LOG", str(log))
    (config.problem_dir / ".env").write_text("OPENROUTER_API_KEY=test-key\n")
    monkeypatch.chdir(config.problem_dir)
    scorer_provider.replies.append([("Double.", 7.0)])
    botbox_script.advice.extend(["Double."] * 2)
    botbox_script.solutions.extend(["print(int(input()) * 2)"] * 4)
    await main(
        [
            "--window-forks",
            "1",
            "--window-solo-turns",
            "2",
            "-U",
            "selected-u",
            "-T",
            "selected-t",
            "--cap-strategy",
            "surprisal",
            "--scorer-base-url",
            "http://scorer/v1",
            "--max-u-turns",
            "1",
            "--t-samples",
            "2",
            "--t-pool-size",
            "1",
            "--output",
            str(config.output),
            str(config.problem_dir),
        ]
    )
    settings = json.loads((config.output / "settings.json").read_text())
    assert settings["window_solo_turns"] == 2
    assert "window_turns" not in settings
    result = json.loads(config.result_file.read_text())
    assert result["success"] and result["attempts"] == 2
    assert result["cap_strategy"] == "surprisal"
    assert result["best_measurement"] == pytest.approx(7.0)
    assert len(botbox_script.sessions) == 4
    blocks = [json.loads(line) for line in log.read_text().splitlines()]
    starts = {block["id"]: block for block in blocks if block.get("phase") == "start"}
    stops = {block["id"] for block in blocks if block.get("phase") == "stop"}
    assert starts.keys() == stops
    streams = {block_id.rsplit("/", 1)[0] for block_id in starts}
    assert len([stream for stream in streams if stream.endswith("/u")]) == 2
    assert len([stream for stream in streams if "/ts/" in stream]) == 4
    assert {"thinking", "text"} <= {block["type"] for block in starts.values()}
    assert all(request["model"] == "selected-u" for request in chat_provider)
    assert scorer_provider.requests[0]["model"] == "selected-t"


async def test_surprisal_reads_scorer_url_from_labnotes_state(
    config, botbox_script, scorer_provider, chat_provider, monkeypatch, tmp_path
):
    (config.problem_dir / ".env").write_text("OPENROUTER_API_KEY=test-key\n")
    monkeypatch.chdir(config.problem_dir)
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"base_url": "http://state-scorer/v1"}))
    monkeypatch.setenv("LABNOTES_RUN_STATE", str(state))
    scorer_provider.replies.append([("Double.", 7.0)])
    botbox_script.advice.extend(["Double."] * 2)
    botbox_script.solutions.extend(["print(int(input()) * 2)"] * 4)
    await main(
        [
            "--window-forks",
            "1",
            "--window-solo-turns",
            "2",
            "--cap-strategy",
            "surprisal",
            "--max-u-turns",
            "1",
            "--t-samples",
            "2",
            "--t-pool-size",
            "1",
            "--output",
            str(config.output),
            str(config.problem_dir),
        ]
    )
    settings = json.loads((config.output / "settings.json").read_text())
    assert settings["scorer_base_url"] == "http://state-scorer/v1"


def test_rejects_nonpositive_stopping_budget(config):
    with pytest.raises(ValidationError, match="max_u_turns"):
        Config(**(config.model_dump() | {"max_u_turns": 0}))


def test_surprisal_requires_endpoint(config):
    with pytest.raises(ValidationError, match="scorer_base_url"):
        Config(**(config.model_dump() | {"cap_strategy": "surprisal"}))
