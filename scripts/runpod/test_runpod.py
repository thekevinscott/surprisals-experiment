import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import teardown

spec = importlib.util.spec_from_file_location("runpod_setup", Path(__file__).with_name("setup.py"))
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def response(status=200, body=None):
    return httpx.Response(status, json=body, request=httpx.Request("GET", "https://example.com"))


@pytest.fixture(autouse=True)
def fake_http(monkeypatch):
    request = Mock()
    monkeypatch.setattr(teardown.httpx, "request", request)
    monkeypatch.setattr(teardown, "api_key", lambda: "test-key")
    monkeypatch.setattr(teardown.time, "sleep", lambda _: None)
    return request


def test_create_and_wait(fake_http, capsys):
    fake_http.side_effect = [response(body={"id": "pod1"}), response(503), response(body={"data": []})]
    setup.main([])
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
    setup.main(["--model", "small", "--gpu", "cheap"])
    payload = fake_http.call_args_list[0].kwargs["json"]
    assert payload["gpuTypeIds"] == ["cheap"]
    assert "small" in payload["dockerStartCmd"]


@pytest.mark.parametrize("failure", [RuntimeError("startup"), KeyboardInterrupt()])
def test_startup_cleanup(fake_http, failure):
    fake_http.side_effect = [response(body={"id": "pod1"}), failure, response(204), response(404)]
    with pytest.raises(type(failure)):
        setup.main([])
    assert fake_http.call_args_list[2].args == ("DELETE", teardown.API + "/pods/pod1")
    assert fake_http.call_args_list[3].args == ("GET", teardown.API + "/pods/pod1")


def test_readiness_timeout_cleans_up(fake_http, monkeypatch):
    monkeypatch.setattr(setup, "READY_TIMEOUT", 0)
    fake_http.side_effect = [response(body={"id": "pod1"}), response(204), response(404)]
    with pytest.raises(TimeoutError):
        setup.main([])


def test_teardown_waits_until_gone(fake_http):
    fake_http.side_effect = [response(204), response(body={"id": "pod1"}), response(404)]
    teardown.main(["pod1"])
    assert fake_http.call_count == 3


def test_teardown_not_gone_fails(fake_http, monkeypatch):
    monkeypatch.setattr(teardown, "DELETE_TIMEOUT", 0)
    fake_http.return_value = response(204)
    with pytest.raises(TimeoutError):
        teardown.main(["pod1"])


def test_teardown_api_failure(fake_http):
    fake_http.return_value = response(403)
    with pytest.raises(httpx.HTTPStatusError):
        teardown.main(["pod1"])
