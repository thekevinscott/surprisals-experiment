# /// script
# dependencies = ["httpx", "python-dotenv"]
# ///
"""uv run scripts/runpod/setup.py [--model MODEL] [--gpu GPU_ID]"""

import argparse
import json
import time

import httpx

import teardown

READY_TIMEOUT = 1800


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="openai/gpt-oss-120b")
    parser.add_argument("--gpu", default="NVIDIA H100 80GB HBM3")
    args = parser.parse_args(argv)
    key = teardown.api_key()
    result = teardown.request("POST", f"{teardown.API}/pods", key, json={
        "name": "surprisal-scorer",
        "imageName": "vllm/vllm-openai:v0.30.0",
        "cloudType": "SECURE",
        "computeType": "GPU",
        "gpuTypeIds": [args.gpu],
        "gpuCount": 1,
        "containerDiskInGb": 100,
        "volumeInGb": 0,
        "ports": ["8000/http"],
        "dockerEntrypoint": ["python3", "-m", "vllm.entrypoints.openai.api_server"],
        "dockerStartCmd": [
            "--model", args.model,
            "--host", "0.0.0.0", "--port", "8000",
            "--max-model-len", "8192",
            "--enable-chunked-prefill",
            "--max-num-batched-tokens", "8192",
            "--gpu-memory-utilization", "0.85",
        ],
    })
    result.raise_for_status()
    pod_id = result.json()["id"]
    base_url = f"https://{pod_id}-8000.proxy.runpod.net/v1"
    try:
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
        print(json.dumps({"pod_id": pod_id, "base_url": base_url}), flush=True)
    except BaseException:
        teardown.delete_pod(pod_id, key)
        raise


if __name__ == "__main__":
    main()
