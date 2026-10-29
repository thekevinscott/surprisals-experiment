"""Create a vLLM scorer and wait for readiness."""

import time
import sys

import httpx
import labnotes

from . import teardown

READY_TIMEOUT = 1800


DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_GPU = "NVIDIA H100 80GB HBM3"


def create_pod(model, gpu, key):
    result = teardown.request("POST", f"{teardown.API}/pods", key, json={
        "name": "surprisal-scorer",
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
            "--model", model,
            "--host", "0.0.0.0", "--port", "8000",
            "--max-model-len", "8192",
            "--enable-chunked-prefill",
            "--max-num-batched-tokens", "8192",
            "--gpu-memory-utilization", "0.85",
        ],
    })
    result.raise_for_status()
    pod_id = result.json()["id"]
    print(f"Created pod {pod_id}", file=sys.stderr, flush=True)
    return pod_id


def up(model=DEFAULT_MODEL, gpu=DEFAULT_GPU):
    key = teardown.api_key()
    pod_id = create_pod(model, gpu, key)
    try:
        labnotes.set_state({"pod_id": pod_id})
        base_url = f"https://{pod_id}-8000.proxy.runpod.net/v1"
        deadline = time.monotonic() + READY_TIMEOUT
        while time.monotonic() < deadline:
            try:
                ready = teardown.request("GET", f"{base_url}/models")
                ready.raise_for_status()
                break
            except (httpx.HTTPError, OSError):
                time.sleep(10)
        else:
            raise TimeoutError(f"Pod {pod_id} did not become ready")
        labnotes.set_state({"base_url": base_url})
    except BaseException:
        teardown.delete_pod(pod_id, key)
        raise
