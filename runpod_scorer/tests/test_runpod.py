import asyncio
import json
import os
from contextlib import asynccontextmanager, nullcontext
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event
from unittest.mock import Mock

import httpx
import pytest
from runpod_scorer.cli import main

from runpod_scorer import logs, setup, teardown, users


def response(status=200, body=None):
    return httpx.Response(
        status, json=body, request=httpx.Request("GET", "https://example.com")
    )


@pytest.fixture(autouse=True)
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    monkeypatch.setattr(users, "daemon_pid", os.getpid)
    path = tmp_path / "state.json"
    monkeypatch.setenv("LABNOTES_STATE", str(path))
    return path


def read(state):
    return json.loads(state.read_text())


@pytest.fixture
def pod_state(state):
    state.write_text(json.dumps({"pod_id": "pod1"}))
    users.register("pod1", state.parent, os.getpid())


@pytest.fixture(autouse=True)
def fake_http(monkeypatch):
    request = Mock()
    monkeypatch.setattr(teardown.httpx, "request", request)
    monkeypatch.setenv("RUNPOD_API_KEY", "test-key")
    monkeypatch.setattr(teardown, "load_dotenv", Mock())
    monkeypatch.setattr(teardown.time, "sleep", lambda _: None)
    return request


LOG_STREAM = (
    b"id: 2026-11-06T10:00:00Z/1\n"
    b'data: {"ts":"2026-11-06T10:00:00Z","source":"system","line":"pulling image"}\n\n'
    b"id: 2026-11-06T10:20:00Z/2\n"
    b'data: {"ts":"2026-11-06T10:20:00Z","source":"container","line":"Loading weights"}\n\n'
)


@pytest.fixture(autouse=True)
def fake_stream(monkeypatch):
    stream = Mock(
        side_effect=lambda *args, **kwargs: nullcontext(
            httpx.Response(200, content=LOG_STREAM, request=httpx.Request(*args))
        )
    )
    monkeypatch.setattr(logs.httpx, "stream", stream)
    return stream


def test_create_and_wait(fake_http, state):
    fake_http.side_effect = [
        response(body=[]),
        response(body={"id": "pod1"}),
        response(503),
        response(body={}),
        response(body={"data": []}),
    ]
    main(["up"])
    calls = fake_http.call_args_list
    payload = calls[1].kwargs["json"]
    assert payload["imageName"] == "vllm/vllm-openai:v0.30.0"
    assert payload["gpuTypeIds"] == ["NVIDIA H100 80GB HBM3"]
    assert payload["gpuCount"] == 1
    assert payload["ports"] == ["8000/http"]
    assert "openai/gpt-oss-120b" in payload["dockerStartCmd"]
    assert calls[-1].args[1] == "https://pod1-8000.proxy.runpod.net/v1/models"
    assert "Authorization" not in calls[-1].kwargs["headers"]
    assert read(state) == {
        "pod_id": "pod1",
        "base_url": "https://pod1-8000.proxy.runpod.net/v1",
    }


def test_override(fake_http):
    fake_http.side_effect = [
        response(body=[]),
        response(body={"id": "pod1"}),
        response(),
    ]
    main(["up", "--model", "small", "--gpu", "cheap"])
    payload = fake_http.call_args_list[1].kwargs["json"]
    assert payload["gpuTypeIds"] == ["cheap"]
    assert "small" in payload["dockerStartCmd"]


@pytest.mark.parametrize("failure", [RuntimeError("startup"), KeyboardInterrupt()])
def test_startup_cleanup(fake_http, failure):
    fake_http.side_effect = [
        response(body=[]),
        response(body={"id": "pod1"}),
        failure,
        response(204),
        response(404),
    ]
    with pytest.raises(type(failure)):
        main(["up"])
    assert fake_http.call_args_list[3].args == ("DELETE", teardown.API + "/pods/pod1")
    assert fake_http.call_args_list[4].args == ("GET", teardown.API + "/pods/pod1")


def test_readiness_timeout_cleans_up(fake_http, monkeypatch):
    monkeypatch.setattr(setup, "READY_TIMEOUT", 0)
    fake_http.side_effect = [
        response(body=[]),
        response(body={"id": "pod1"}),
        response(204),
        response(404),
    ]
    with pytest.raises(TimeoutError):
        main(["up"])


def test_teardown_waits_until_gone(fake_http, pod_state):
    fake_http.side_effect = [
        response(204),
        response(body={"id": "pod1"}),
        response(404),
    ]
    main(["down"])
    assert fake_http.call_count == 3


def test_teardown_not_gone_fails(fake_http, pod_state, monkeypatch):
    monkeypatch.setattr(teardown, "DELETE_TIMEOUT", 0)
    fake_http.return_value = response(204)
    with pytest.raises(TimeoutError):
        main(["down"])


def test_teardown_api_failure(fake_http, pod_state):
    fake_http.return_value = response(403)
    with pytest.raises(httpx.HTTPStatusError):
        main(["down"])


def test_readiness_transport_retry(fake_http):
    fake_http.side_effect = [
        response(body=[]),
        response(body={"id": "pod1"}),
        httpx.ConnectError("not listening yet"),
        response(body={}),
        response(),
    ]
    main(["up"])
    assert fake_http.call_count == 5


def test_up_timestamps_each_step(fake_http, capsys):
    fake_http.side_effect = [
        response(body=[]),
        response(body={"id": "pod1"}),
        httpx.ConnectError("not listening yet"),
        response(body={"lastStatusChange": "Rented by User"}),
        response(502),
        response(body={"lastStatusChange": "Rented by User", "portMappings": {}}),
        response(502),
        response(
            body={
                "lastStatusChange": "Rented by User",
                "lastStartedAt": "2026-11-06T10:05:00Z",
                "portMappings": {},
            }
        ),
        response(),
    ]
    main(["up"])
    lines = capsys.readouterr().err.splitlines()
    stamps = [datetime.fromisoformat(line.split(" ", 1)[0]) for line in lines]
    assert all(stamp.utcoffset() == timedelta(0) for stamp in stamps)
    assert [line.split(" ", 1)[1] for line in lines] == [
        "Created pod pod1",
        "Pod pod1 not ready: ConnectError",
        "Pod pod1 lastStatusChange: Rented by User",
        "Pod pod1 not ready: 502",
        "Pod pod1 portMappings: {}",
        "Pod pod1 lastStartedAt: 2026-11-06T10:05:00Z",
        "Pod pod1 ready",
    ]
    assert fake_http.call_args_list[3].args == ("GET", teardown.API + "/pods/pod1")
    assert (
        fake_http.call_args_list[3].kwargs["headers"]["Authorization"]
        == "Bearer test-key"
    )


def test_status_failure_keeps_waiting(fake_http):
    fake_http.side_effect = [
        response(body=[]),
        response(body={"id": "pod1"}),
        response(502),
        response(500),
        response(),
    ]
    main(["up"])
    assert fake_http.call_count == 5


def test_fast_up_saves_no_logs(fake_http, fake_stream, state):
    fake_http.side_effect = [
        response(body=[]),
        response(body={"id": "pod1"}),
        response(),
    ]
    main(["up"])
    fake_stream.assert_not_called()
    assert not (state.parent / "runpod-logs.jsonl").exists()


def test_slow_up_saves_logs(fake_http, fake_stream, state, monkeypatch, capsys):
    monkeypatch.setattr(setup, "SLOW_START", -1)
    fake_http.side_effect = [
        response(body=[]),
        response(body={"id": "pod1"}),
        response(),
    ]
    main(["up"])
    call = fake_stream.call_args
    assert call.args == ("GET", "https://api.runpod.io/v2/pods/pod1/logs")
    assert call.kwargs["headers"]["Authorization"] == "Bearer test-key"
    saved = (state.parent / "runpod-logs.jsonl").read_text().splitlines()
    assert [json.loads(line)["line"] for line in saved] == [
        "pulling image",
        "Loading weights",
    ]
    assert read(state)["base_url"] == "https://pod1-8000.proxy.runpod.net/v1"
    assert "Saved pod pod1 logs" in capsys.readouterr().err


def test_failed_up_saves_logs_before_delete(fake_http, fake_stream, state, monkeypatch):
    monkeypatch.setattr(setup, "READY_TIMEOUT", 0)
    fake_stream.side_effect = lambda *args, **kwargs: (
        nullcontext(
            httpx.Response(200, content=LOG_STREAM, request=httpx.Request(*args))
        )
        if fake_http.call_count == 2
        else pytest.fail("logs fetched after delete")
    )
    fake_http.side_effect = [
        response(body=[]),
        response(body={"id": "pod1"}),
        response(204),
        response(404),
    ]
    with pytest.raises(TimeoutError):
        main(["up"])
    assert (state.parent / "runpod-logs.jsonl").exists()
    assert fake_http.call_args_list[2].args == ("DELETE", teardown.API + "/pods/pod1")


def test_log_failure_does_not_fail_up(
    fake_http, fake_stream, state, monkeypatch, capsys
):
    monkeypatch.setattr(setup, "SLOW_START", -1)
    fake_stream.side_effect = httpx.ConnectError("refused")
    fake_http.side_effect = [
        response(body=[]),
        response(body={"id": "pod1"}),
        response(),
    ]
    main(["up"])
    assert "base_url" in read(state)
    assert "Pod pod1 logs not saved" in capsys.readouterr().err


def test_create_failure_does_not_delete(fake_http):
    fake_http.side_effect = [response(body=[]), response(500)]
    with pytest.raises(httpx.HTTPStatusError):
        main(["up"])
    assert fake_http.call_count == 2


def test_api_key_stays_on_control_plane(fake_http):
    fake_http.side_effect = [
        response(body=[]),
        response(body={"id": "pod1"}),
        response(),
    ]
    main(["up"])
    assert (
        fake_http.call_args_list[0].kwargs["headers"]["Authorization"]
        == "Bearer test-key"
    )
    assert "Authorization" not in fake_http.call_args_list[2].kwargs["headers"]


def test_loads_repo_env(monkeypatch):
    load = Mock()
    monkeypatch.setattr(teardown, "load_dotenv", load)
    monkeypatch.setenv("RUNPOD_API_KEY", "fake")
    assert teardown.api_key() == "fake"
    load.assert_called_once_with(Path(teardown.__file__).resolve().parents[3] / ".env")


def test_pod_id_saved_before_readiness(fake_http, state, capsys):
    def respond(method, url, **kwargs):
        if url == teardown.API + "/pods" and method == "GET":
            return response(body=[])
        if method == "POST":
            return response(body={"id": "pod1"})
        assert capsys.readouterr().err.endswith(" Created pod pod1\n")
        assert read(state) == {"pod_id": "pod1"}
        return response()

    fake_http.side_effect = respond
    main(["up"])


@pytest.mark.parametrize("status", [500, 502, 503])
def test_delete_retries_server_errors(fake_http, pod_state, monkeypatch, status):
    sleep = Mock()
    monkeypatch.setattr(teardown.time, "sleep", sleep)
    fake_http.side_effect = [
        response(status),
        response(status),
        response(204),
        response(404),
    ]
    main(["down"])
    assert [call.args for call in sleep.call_args_list] == [(1,), (2,)]
    assert [call.args[0] for call in fake_http.call_args_list] == ["DELETE"] * 3 + [
        "GET"
    ]


def test_delete_exhausts_server_errors(fake_http, pod_state):
    fake_http.return_value = response(503)
    with pytest.raises(httpx.HTTPStatusError):
        main(["down"])
    assert fake_http.call_count == 3


@pytest.mark.parametrize("contents", [None, {}])
def test_down_without_pod_does_nothing(fake_http, state, contents):
    if contents is not None:
        state.write_text(json.dumps(contents))
    teardown.down()
    fake_http.assert_not_called()
    teardown.load_dotenv.assert_not_called()


def test_startup_failure_keeps_pod_id(fake_http, state):
    fake_http.side_effect = [
        response(body=[]),
        response(body={"id": "pod1"}),
        RuntimeError("startup"),
        response(503),
        response(503),
        response(503),
    ]
    with pytest.raises(httpx.HTTPStatusError):
        setup.up()
    assert read(state) == {"pod_id": "pod1"}


def test_up_outside_setup_does_not_create_pod(fake_http, monkeypatch):
    monkeypatch.delenv("LABNOTES_STATE")
    fake_http.side_effect = [
        response(body=[]),
        response(body={"id": "pod1"}),
        response(204),
        response(404),
    ]
    with pytest.raises(RuntimeError):
        setup.up()
    fake_http.assert_not_called()


def scorer(model=setup.DEFAULT_MODEL, pod_id="pod1", status="RUNNING"):
    return {
        "id": pod_id,
        "name": "surprisal-scorer-24k",
        "desiredStatus": status,
        "dockerStartCmd": ["--model", model],
    }


def test_reuses_existing_scorer(fake_http, state):
    fake_http.side_effect = [response(body=[scorer()]), response()]
    main(["up"])
    assert [call.args[0] for call in fake_http.call_args_list] == ["GET", "GET"]
    assert read(state)["pod_id"] == "pod1"
    user = json.loads(users.user_file("pod1", state.parent).read_text())
    assert user == {"state_dir": str(state.parent), "pid": os.getpid()}


@pytest.mark.parametrize(
    "pods, message",
    [
        ([scorer(model="other-model")], "other-model"),
        ([scorer(status="EXITED")], "EXITED"),
        ([scorer(), scorer(pod_id="pod2")], "Multiple"),
    ],
)
def test_refuses_to_create_a_second_pod(fake_http, pods, message):
    fake_http.return_value = response(body=pods)
    with pytest.raises(RuntimeError, match=message):
        main(["up"])
    assert [call.args[0] for call in fake_http.call_args_list] == ["GET"]


def test_list_failure_does_not_create(fake_http):
    fake_http.return_value = response(503)
    with pytest.raises(httpx.HTTPStatusError):
        main(["up"])
    assert [call.args[0] for call in fake_http.call_args_list] == ["GET"]


def test_down_keeps_another_live_user(fake_http, state, pod_state, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    users.register("pod1", other, os.getpid())
    main(["down"])
    fake_http.assert_not_called()
    assert not users.user_file("pod1", state.parent).exists()
    assert users.user_file("pod1", other).exists()


def test_failed_startup_keeps_another_live_user(fake_http, state, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    users.register("pod1", other, os.getpid())
    fake_http.side_effect = [response(body=[scorer()]), RuntimeError("startup")]
    with pytest.raises(RuntimeError, match="startup"):
        main(["up"])
    assert not users.user_file("pod1", state.parent).exists()
    assert users.user_file("pod1", other).exists()
    assert [call.args[0] for call in fake_http.call_args_list] == ["GET", "GET"]


@pytest.mark.parametrize("dead", ["pid", "folder"])
def test_reap_removes_dead_users_and_deletes(fake_http, tmp_path, monkeypatch, dead):
    import subprocess
    import sys

    folder = tmp_path / "ended"
    folder.mkdir()
    pid = os.getpid()
    if dead == "pid":
        process = subprocess.Popen([sys.executable, "-c", "pass"])
        process.wait(timeout=10)
        pid = process.pid
    else:
        folder.rmdir()
    users.register("pod1", folder, pid)
    monkeypatch.delenv("LABNOTES_STATE")
    fake_http.side_effect = [response(body=[scorer()]), response(204), response(404)]
    main(["reap"])
    assert not users.user_file("pod1", folder).exists()
    assert [call.args[0] for call in fake_http.call_args_list] == [
        "GET",
        "DELETE",
        "GET",
    ]


def test_reap_keeps_live_users_and_ignores_other_pods(fake_http, pod_state):
    fake_http.return_value = response(
        body=[scorer(), {"id": "other", "name": "unrelated"}]
    )
    main(["reap"])
    assert fake_http.call_count == 1


def test_down_prunes_dead_users_before_deleting(fake_http, pod_state, tmp_path):
    users.register("pod1", tmp_path / "removed-folder", os.getpid())
    fake_http.side_effect = [response(204), response(404)]
    main(["down"])
    assert not users.remaining("pod1")
    assert [call.args[0] for call in fake_http.call_args_list] == ["DELETE", "GET"]


def test_concurrent_up_creates_once_and_waits_outside_lock(fake_http, tmp_path):
    import multiprocessing
    from threading import Event

    context = multiprocessing.get_context("fork")
    with context.Manager() as manager:
        pods = manager.list()
        calls = manager.list()
        start = context.Barrier(2)
        ready = context.Queue()
        release = context.Event()

        def api(method, url, **kwargs):
            calls.append((method, url))
            if url == teardown.API + "/pods":
                if method == "GET":
                    snapshot = list(pods)
                    # Widen the list/create race without mocking the real flock.
                    Event().wait(0.1)
                    return response(body=snapshot)
                pod_id = f"pod{len(pods) + 1}"
                pods.append(kwargs["json"] | {"id": pod_id, "desiredStatus": "RUNNING"})
                return response(body={"id": pod_id})
            ready.put(os.getpid())
            assert release.wait(10), "readiness wait held scorer.lock"
            return response()

        fake_http.side_effect = api

        def invoke(index):
            folder = tmp_path / str(index)
            folder.mkdir()
            os.environ["LABNOTES_STATE"] = str(folder / "state.json")
            start.wait(timeout=10)
            setup.up()

        processes = [
            context.Process(target=invoke, args=(index,)) for index in range(2)
        ]
        try:
            for process in processes:
                process.start()
            assert ready.get(timeout=10) != ready.get(timeout=10)
            release.set()
            for process in processes:
                process.join(timeout=10)
                assert process.exitcode == 0
            assert len(pods) == 1
            assert sum(method == "POST" for method, _ in calls) == 1
            assert len(list((Path.home() / ".runpod/users/pod1").glob("*.json"))) == 2
        finally:
            release.set()
            for process in processes:
                if process.is_alive():
                    process.terminate()
                process.join(timeout=10)


def test_no_daemon_does_not_create(fake_http, monkeypatch):
    monkeypatch.setattr(
        users, "daemon_pid", Mock(side_effect=RuntimeError("No parent labnotes daemon"))
    )
    with pytest.raises(RuntimeError, match="No parent labnotes daemon"):
        setup.up()
    fake_http.assert_not_called()


def test_repeated_up_for_same_invocation_registers_once(fake_http, state):
    fake_http.side_effect = [
        response(body=[scorer()]),
        response(),
        response(body=[scorer()]),
        response(),
    ]
    setup.up()
    setup.up()
    assert users.remaining("pod1") == [users.user_file("pod1", state.parent)]


@pytest.mark.parametrize("failure", [False, True])
def test_live_logs_do_not_block_readiness_or_survive_setup(
    fake_http, monkeypatch, capsys, failure
):
    waiting = Event()
    closed = Event()

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield LOG_STREAM
            waiting.set()
            await asyncio.Event().wait()

        async def aclose(self):
            closed.set()

    @asynccontextmanager
    async def stream(client, method, url, **kwargs):
        assert url == "https://api.runpod.io/v2/pods/pod1/logs"
        assert kwargs["headers"]["Authorization"] == "Bearer test-key"
        result = httpx.Response(200, stream=Stream(), request=httpx.Request(method, url))
        try:
            yield result
        finally:
            await result.aclose()

    monkeypatch.setattr(httpx.AsyncClient, "stream", stream)

    def ready(*args, **kwargs):
        assert waiting.wait(2), "container logs were not streamed during readiness"
        output = capsys.readouterr().err
        assert "Pod pod1 log: Loading weights" in output
        assert "Pod pod1 log: pulling image" not in output
        if failure:
            raise RuntimeError("startup")
        return response()

    fake_http.side_effect = [response(body=[]), response(body={"id": "pod1"})]
    initial = fake_http.side_effect

    def request(*args, **kwargs):
        if fake_http.call_count <= 2:
            return next(initial)
        if fake_http.call_count == 3:
            return ready(*args, **kwargs)
        return response(204 if args[0] == "DELETE" else 404)

    fake_http.side_effect = request
    if failure:
        with pytest.raises(RuntimeError, match="startup"):
            main(["up"])
    else:
        main(["up"])
    assert closed.is_set(), "log stream survived readiness/failure"


def test_live_log_error_is_reported_once_and_readiness_continues(
    fake_http, monkeypatch, capsys, state
):
    attempted = Event()

    @asynccontextmanager
    async def stream(*args, **kwargs):
        attempted.set()
        raise httpx.ConnectError("logs unavailable")
        yield

    monkeypatch.setattr(httpx.AsyncClient, "stream", stream)

    def request(method, url, **kwargs):
        if url == teardown.API + "/pods":
            return response(body=[] if method == "GET" else {"id": "pod1"})
        assert attempted.wait(2), "live logs were not requested"
        return response()

    fake_http.side_effect = request
    main(["up"])
    assert read(state)["base_url"] == "https://pod1-8000.proxy.runpod.net/v1"
    assert capsys.readouterr().err.count("Pod pod1 log stream failed:") == 1
