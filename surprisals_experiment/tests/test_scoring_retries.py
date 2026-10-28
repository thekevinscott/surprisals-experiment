import asyncio
import importlib
import json
from unittest.mock import AsyncMock

import httpx2
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError

from surprisals_experiment.config import Config
from surprisals_experiment.sdk import run_experiment


@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep)
    return sleep


def status_error(code):
    return APIStatusError("scorer failed", response=httpx2.Response(
        code, request=httpx2.Request("POST", "http://scorer/v1/completions")), body=None)


@pytest.fixture
def scoring_config(config):
    return Config(**(config.model_dump() | {
        "cap_strategy": "surprisal", "scorer_base_url": "http://scorer/v1",
    }))


@pytest.mark.parametrize("failure", [
    APIConnectionError(request=httpx2.Request("POST", "http://scorer")),
    APITimeoutError(request=httpx2.Request("POST", "http://scorer")),
    *[status_error(code) for code in (429, 500, 502, 503)],
])
async def test_transient_scorer_failure_retries_with_advice_saved(
    scoring_config, botbox_script, monkeypatch, no_retry_wait, failure,
):
    config = scoring_config
    calls = 0

    async def score(advice, **kwargs):
        nonlocal calls
        calls += 1
        assert (config.advice_dir(0, 0) / "advice.txt").read_text() == advice
        if calls == 1:
            raise failure
        return [(advice, 10.0)]

    monkeypatch.setattr(importlib.import_module("surprisals_experiment.sdk.advice_measure"),
                        "measure_surprisal", score)
    botbox_script.advice.append("Use a loop")
    botbox_script.solutions.append("print(int(input())*2)")
    deltas = []
    assert await run_experiment(config, on_delta=lambda *event: deltas.append(event))
    assert calls == 2
    no_retry_wait.assert_awaited_once_with(10)
    assert any(kind == "retry" and "1/8 in 10s" in text for kind, text in deltas)
    assert json.loads((config.advice_dir(0, 0) / "metadata.json").read_text()) == {
        "rejected": False, "measurement": 10.0, "tokens": [["Use a loop", 10.0]],
    }


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
async def test_permanent_scorer_error_preserves_advice(
    scoring_config, botbox_script, monkeypatch, no_retry_wait, code,
):
    scorer = AsyncMock(side_effect=status_error(code))
    monkeypatch.setattr(importlib.import_module("surprisals_experiment.sdk.advice_measure"),
                        "measure_surprisal", scorer)
    botbox_script.advice.append("preserve me")
    with pytest.raises(APIStatusError):
        await run_experiment(scoring_config, on_delta=None)
    assert (scoring_config.advice_dir(0, 0) / "advice.txt").read_text() == "preserve me"
    assert scorer.await_count == 1
    no_retry_wait.assert_not_awaited()


async def test_scorer_exhaustion_uses_fixed_budget(
    scoring_config, botbox_script, monkeypatch, no_retry_wait,
):
    retries = 8
    error = status_error(503)
    scorer = AsyncMock(side_effect=error)
    monkeypatch.setattr(importlib.import_module("surprisals_experiment.sdk.advice_measure"),
                        "measure_surprisal", scorer)
    botbox_script.advice.append("preserve me")
    with pytest.raises(RuntimeError, match="Scorer request failed: scorer failed; 8 retries exhausted") as caught:
        await run_experiment(scoring_config, on_delta=None)
    assert caught.value.__cause__ is error
    assert scorer.await_count == retries + 1
    assert [c.args[0] for c in no_retry_wait.await_args_list] == [10, 30, 60, 120, 300, 600, 1800, 3600]
    assert (scoring_config.advice_dir(0, 0) / "advice.txt").read_text() == "preserve me"


async def test_identical_advice_cannot_improve_from_score_jitter(scoring_config, botbox_script, monkeypatch):
    config = scoring_config
    config.max_u_turns = 3
    config.max_turns_without_improvement = 1
    scorer = AsyncMock(side_effect=[[("same", 4.0), (" advice", 6.0)], [("same advice", 9.0)]])
    monkeypatch.setattr(importlib.import_module("surprisals_experiment.sdk.advice_measure"),
                        "measure_surprisal", scorer)
    botbox_script.advice.extend(["same advice"] * 2)
    botbox_script.solutions.extend(["print(int(input())*2)"] * 2)
    assert await run_experiment(config, on_delta=None) == config.t_dir(0, 0) / "src"
    assert scorer.await_count == 1
    assert json.loads(config.result_file.read_text())["attempts"] == 2
    for attempt in range(2):
        metadata = json.loads((config.advice_dir(attempt, 0) / "metadata.json").read_text())
        assert metadata["measurement"] == 10.0
        assert metadata["tokens"] == [["same", 4.0], [" advice", 6.0]]
        assert "Your advice cost 10.0 bits:\nsame<4.0> advice<6.0>" in (
            config.attempt_dir(attempt) / "feedback.txt"
        ).read_text()
    assert "Turns without improvement: 1 of 1." in (config.attempt_dir(1) / "feedback.txt").read_text()


async def test_character_scoring_unchanged(config, botbox_script, monkeypatch):
    scorer = AsyncMock()
    monkeypatch.setattr(importlib.import_module("surprisals_experiment.sdk.advice_measure"),
                        "measure_surprisal", scorer)
    botbox_script.advice.append("Use a loop")
    botbox_script.solutions.append("print(int(input())*2)")
    await run_experiment(config, on_delta=None)
    assert json.loads((config.advice_dir(0, 0) / "metadata.json").read_text()) == {
        "rejected": False, "measurement": 10,
    }
    scorer.assert_not_awaited()


@pytest.mark.parametrize("code, expected_calls", [(408, 1), (409, 1), (429, 9), (503, 9)])
async def test_real_scorer_sdk_does_not_add_retries(scoring_config, monkeypatch, no_retry_wait, code, expected_calls):
    client = scoring_config.advice_measure.client
    calls = []

    def respond(request):
        calls.append(request)
        return httpx2.Response(code, json={"error": {"message": "scorer failed"}})

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(respond)) as http:
        monkeypatch.setattr(client._openai, "_client", http)
        with pytest.raises(RuntimeError if code in (429, 503) else APIStatusError):
            await scoring_config.advice_measure.score("advice")
    assert len(calls) == expected_calls
    assert no_retry_wait.await_count == expected_calls - 1
