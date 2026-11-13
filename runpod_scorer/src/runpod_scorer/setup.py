"""Create a vLLM scorer and wait for readiness."""

import asyncio
import time
from contextlib import suppress

import httpx
import labnotes

from . import costs, teardown, users
from .logs import save_logs, stream_logs
from .timestamp import timestamp

READY_TIMEOUT = 1800
SLOW_START = 600
STEP_FIELDS = ("lastStatusChange", "lastStartedAt", "portMappings")


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
    return result.json()


def up(model=DEFAULT_MODEL, gpu=DEFAULT_GPU, experiment="experiments/surprisal"):
    folder = users.state_directory()
    pid = users.daemon_pid()
    key = teardown.api_key()
    pod_id = None
    started = None
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
                pod = create_pod(model, gpu, key)
                pod_id = pod["id"]
            users.register(pod_id, folder, pid)
            labnotes.set_state({"pod_id": pod_id})
            costs.record(pod, experiment, gpu)
        base_url = f"https://{pod_id}-8000.proxy.runpod.net/v1"
        started = time.monotonic()
        deadline = started + READY_TIMEOUT
        asyncio.run(wait_ready(pod_id, key, base_url, deadline))
        if time.monotonic() - started > SLOW_START:
            save_logs(pod_id, key, folder)
        labnotes.set_state({"base_url": base_url})
    except BaseException:
        if started is not None:
            save_logs(pod_id, key, folder)
        if pod_id is not None:
            with users.locked():
                teardown.release(pod_id, key, users.user_file(pod_id, folder))
        raise


async def wait_ready(pod_id, key, base_url, deadline):
    logs = asyncio.create_task(stream_logs(pod_id, key))
    try:
        last = None
        steps = {}
        while time.monotonic() < deadline:
            try:
                ready = await asyncio.to_thread(teardown.request, "GET", f"{base_url}/models")
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
                try:
                    pod = await asyncio.to_thread(
                        teardown.request, "GET", f"{teardown.API}/pods/{pod_id}", key
                    )
                    pod.raise_for_status()
                    pod = pod.json()
                except (httpx.HTTPError, OSError):
                    pod = {}
                for field in STEP_FIELDS:
                    if field in pod and pod[field] != steps.get(field):
                        timestamp(f"Pod {pod_id} {field}: {pod[field]}")
                        steps[field] = pod[field]
                await asyncio.to_thread(time.sleep, 10)
        else:
            raise TimeoutError(f"Pod {pod_id} did not become ready")
    finally:
        logs.cancel()
        with suppress(asyncio.CancelledError):
            await logs
