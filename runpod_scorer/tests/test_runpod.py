import json
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest

from runpod_scorer import setup, teardown
from runpod_scorer.cli import main


def response(status=200, body=None):
    return httpx.Response(status, json=body, request=httpx.Request("GET", "https://example.com"))


@pytest.fixture(autouse=True)
def invocation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "down-dir").mkdir()
    (tmp_path / "down-dir/runpod.json").write_text(json.dumps({"pod_id": "pod1"}))
    return tmp_path / "up-dir"


@pytest.fixture(autouse=True)
def fake_http(monkeypatch):
    request = Mock()
    monkeypatch.setattr(teardown.httpx, "request", request)
    monkeypatch.setenv("RUNPOD_API_KEY", "test-key")
    monkeypatch.setattr(teardown, "load_dotenv", Mock())
    monkeypatch.setattr(teardown.time, "sleep", lambda _: None)
    return request


def test_create_and_wait(fake_http, capsys):
    fake_http.side_effect = [response(body={"id": "pod1"}), response(503), response(body={"data": []})]
    main(["up", "up-dir"])
    calls = fake_http.call_args_list
    payload = calls[0].kwargs["json"]
    assert payload["imageName"] == "vllm/vllm-openai:v0.30.0"
    assert payload["gpuTypeIds"] == ["NVIDIA H100 80GB HBM3"]
    assert payload["gpuCount"] == 1
    assert payload["ports"] == ["8000/http"]
    assert "openai/gpt-oss-120b" in payload["dockerStartCmd"]
    assert calls[-1].args[1] == "https://pod1-8000.proxy.runpod.net/v1/models"
    assert "Authorization" not in calls[-1].kwargs["headers"]
    assert json.loads(capsys.readouterr().out) == {
        "pod_id": "pod1", "base_url": "https://pod1-8000.proxy.runpod.net/v1",
    }


def test_override(fake_http):
    fake_http.side_effect = [response(body={"id": "pod1"}), response()]
    main(["up", "up-dir", "--model", "small", "--gpu", "cheap"])
    payload = fake_http.call_args_list[0].kwargs["json"]
    assert payload["gpuTypeIds"] == ["cheap"]
    assert "small" in payload["dockerStartCmd"]


@pytest.mark.parametrize("failure", [RuntimeError("startup"), KeyboardInterrupt()])
def test_startup_cleanup(fake_http, failure):
    fake_http.side_effect = [response(body={"id": "pod1"}), failure, response(204), response(404)]
    with pytest.raises(type(failure)):
        main(["up", "up-dir"])
    assert fake_http.call_args_list[2].args == ("DELETE", teardown.API + "/pods/pod1")
    assert fake_http.call_args_list[3].args == ("GET", teardown.API + "/pods/pod1")


def test_readiness_timeout_cleans_up(fake_http, monkeypatch):
    monkeypatch.setattr(setup, "READY_TIMEOUT", 0)
    fake_http.side_effect = [response(body={"id": "pod1"}), response(204), response(404)]
    with pytest.raises(TimeoutError):
        main(["up", "up-dir"])


def test_teardown_waits_until_gone(fake_http):
    fake_http.side_effect = [response(204), response(body={"id": "pod1"}), response(404)]
    main(["down", "down-dir"])
    assert fake_http.call_count == 3


def test_teardown_not_gone_fails(fake_http, monkeypatch):
    monkeypatch.setattr(teardown, "DELETE_TIMEOUT", 0)
    fake_http.return_value = response(204)
    with pytest.raises(TimeoutError):
        main(["down", "down-dir"])


def test_teardown_api_failure(fake_http):
    fake_http.return_value = response(403)
    with pytest.raises(httpx.HTTPStatusError):
        main(["down", "down-dir"])


def test_readiness_transport_retry(fake_http):
    fake_http.side_effect = [
        response(body={"id": "pod1"}),
        httpx.ConnectError("not listening yet"),
        response(),
    ]
    main(["up", "up-dir"])
    assert fake_http.call_count == 3


def test_create_failure_does_not_delete(fake_http):
    fake_http.return_value = response(500)
    with pytest.raises(httpx.HTTPStatusError):
        main(["up", "up-dir"])
    assert fake_http.call_count == 1


def test_api_key_stays_on_control_plane(fake_http):
    fake_http.side_effect = [response(body={"id": "pod1"}), response()]
    main(["up", "up-dir"])
    assert fake_http.call_args_list[0].kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert "Authorization" not in fake_http.call_args_list[1].kwargs["headers"]


def test_loads_repo_env(monkeypatch):
    load = Mock()
    monkeypatch.setattr(teardown, "load_dotenv", load)
    monkeypatch.setenv("RUNPOD_API_KEY", "fake")
    assert teardown.api_key() == "fake"
    load.assert_called_once_with(Path(teardown.__file__).resolve().parents[3] / ".env")


def test_pod_id_printed_before_readiness(fake_http, capsys):
    def respond(method, url, **kwargs):
        if method == "POST":
            return response(body={"id": "pod1"})
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == "Created pod pod1\n"
        return response()
    fake_http.side_effect = respond
    main(["up", "up-dir"])


@pytest.mark.parametrize("status", [500, 502, 503])
def test_delete_retries_server_errors(fake_http, monkeypatch, status):
    sleep = Mock()
    monkeypatch.setattr(teardown.time, "sleep", sleep)
    fake_http.side_effect = [response(status), response(status), response(204), response(404)]
    main(["down", "down-dir"])
    assert [call.args for call in sleep.call_args_list] == [(1,), (2,)]
    assert [call.args[0] for call in fake_http.call_args_list] == ["DELETE"] * 3 + ["GET"]


def test_delete_exhausts_server_errors(fake_http):
    fake_http.return_value = response(503)
    with pytest.raises(httpx.HTTPStatusError):
        main(["down", "down-dir"])
    assert fake_http.call_count == 3


def test_shared_concurrent_up_creates_once(fake_http, invocation, capsys):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Event

    together, waiting, release = Barrier(2), Event(), Event()

    def respond(method, url, **kwargs):
        if method == "POST":
            return response(body={"id": "pod1"})
        waiting.set()
        assert release.wait(3)
        return response()

    def up():
        together.wait(timeout=3)
        return setup.up(invocation)

    fake_http.side_effect = respond
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(up) for _ in range(2)]
        try:
            assert waiting.wait(3)
            assert json.loads((invocation / "runpod.json").read_text()) == {"pod_id": "pod1"}
        finally:
            release.set()
        results = [future.result(timeout=3) for future in futures]
    assert results[0] == results[1]
    assert results[0]["base_url"] == "https://pod1-8000.proxy.runpod.net/v1"
    assert sum(call.args[0] == "POST" for call in fake_http.call_args_list) == 1
    assert [json.loads(line) for line in capsys.readouterr().out.splitlines()] == results
    assert json.loads((invocation / "runpod.json").read_text()) == results[0]


def test_up_reuses_incomplete_state(fake_http, invocation):
    invocation.mkdir()
    (invocation / "runpod.json").write_text('{"pod_id": "existing"}')
    fake_http.side_effect = [response(503), response()]
    pod = setup.up(invocation)
    assert pod["pod_id"] == "existing"
    assert all(call.args[0] == "GET" for call in fake_http.call_args_list)


@pytest.mark.parametrize("exists", [False, True])
def test_down_without_state_does_nothing(fake_http, invocation, exists):
    if exists:
        invocation.mkdir()
    teardown.down(invocation)
    fake_http.assert_not_called()
    teardown.load_dotenv.assert_not_called()


def test_down_removes_state_only_after_verified(fake_http, tmp_path):
    state = tmp_path / "down-dir/runpod.json"

    def respond(method, url, **kwargs):
        assert state.exists()
        return response(204 if method == "DELETE" else 404)

    fake_http.side_effect = respond
    main(["down", "down-dir"])
    assert not state.exists()


def test_failed_deletion_retains_state(fake_http, tmp_path):
    fake_http.return_value = response(503)
    with pytest.raises(httpx.HTTPStatusError):
        main(["down", "down-dir"])
    assert json.loads((tmp_path / "down-dir/runpod.json").read_text()) == {"pod_id": "pod1"}


@pytest.mark.parametrize("cleanup_ok", [True, False])
def test_startup_failure_state_cleanup(fake_http, invocation, cleanup_ok):
    fake_http.side_effect = [
        response(body={"id": "pod1"}), RuntimeError("startup"),
        *([response(204), response(404)] if cleanup_ok else [response(503)] * 3),
    ]
    with pytest.raises((RuntimeError, httpx.HTTPStatusError)):
        setup.up(invocation)
    assert (invocation / "runpod.json").exists() is not cleanup_ok
