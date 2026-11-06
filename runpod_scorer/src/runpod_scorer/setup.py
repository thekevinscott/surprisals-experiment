"""Create a vLLM scorer and wait for readiness."""

import time

import httpx
import labnotes

from . import teardown, users
from .timestamp import timestamp

READY_TIMEOUT = 1800


DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_GPU = "NVIDIA H100 80GB HBM3"


def create_pod(model, gpu, key):
    result = teardown.request(
        "POST",
        f"{teardown.API}/pods",
        key,
        json={
            "name": "surprisal-scorer-24k",
            "imageName": "vllm/vllm-openai:v0.30.0",
            "cloudType": "SECURE",
            "computeType": "GPU",
            "gpuTypeIds": [gpu],
            "gpuCount": 1,
            "containerDiskInGb": 100,
            "volumeInGb": 0,
            "ports": ["8000/http"],
            "dockerEntrypoint": ["python3", "-m", "vllm.entrypoints.openai.api_server"],
            "dockerStartCmd": [
                "--model",
                model,
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--max-model-len",
                "24576",
                "--enable-chunked-prefill",
                "--max-num-batched-tokens",
                "8192",
                "--gpu-memory-utilization",
                "0.85",
            ],
        },
    )
    result.raise_for_status()
    pod_id = result.json()["id"]
    timestamp(f"Created pod {pod_id}")
    return pod_id


def up(model=DEFAULT_MODEL, gpu=DEFAULT_GPU):
    folder = users.state_directory()
    pid = users.daemon_pid()
    key = teardown.api_key()
    pod_id = None
    try:
        with users.locked():
            pods = teardown.scorer_pods(key)
            if len(pods) > 1:
                raise RuntimeError(
                    "Multiple surprisal-scorer-24k pods already exist: "
                    + ", ".join(p["id"] for p in pods)
                )
            if pods:
                pod = pods[0]
                command = pod.get("dockerStartCmd", [])
                existing_model = (
                    command[command.index("--model") + 1]
                    if "--model" in command
                    else None
                )
                if existing_model != model:
                    raise RuntimeError(
                        f"Scorer {pod['id']} serves {existing_model!r}, requested {model!r}; refusing a second pod"
                    )
                if pod["desiredStatus"] != "RUNNING":
                    raise RuntimeError(
                        f"Scorer {pod['id']} is {pod['desiredStatus']}; resume or delete it before up"
                    )
                pod_id = pod["id"]
                timestamp(f"Reusing pod {pod_id}")
            else:
                pod_id = create_pod(model, gpu, key)
            users.register(pod_id, folder, pid)
            labnotes.set_state({"pod_id": pod_id})
        base_url = f"https://{pod_id}-8000.proxy.runpod.net/v1"
        deadline = time.monotonic() + READY_TIMEOUT
        last = None
        while time.monotonic() < deadline:
            try:
                ready = teardown.request("GET", f"{base_url}/models")
                ready.raise_for_status()
                timestamp(f"Pod {pod_id} ready")
                break
            except (httpx.HTTPError, OSError) as error:
                outcome = (
                    error.response.status_code
                    if isinstance(error, httpx.HTTPStatusError)
                    else type(error).__name__
                )
                if outcome != last:
                    timestamp(f"Pod {pod_id} not ready: {outcome}")
                    last = outcome
                time.sleep(10)
        else:
            raise TimeoutError(f"Pod {pod_id} did not become ready")
        labnotes.set_state({"base_url": base_url})
    except BaseException:
        if pod_id is not None:
            with users.locked():
                teardown.release(pod_id, key, users.user_file(pod_id, folder))
        raise
