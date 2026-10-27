# /// script
# dependencies = ["httpx", "python-dotenv"]
# ///
"""uv run scripts/runpod/teardown.py <pod_id>"""

import argparse
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

API = "https://rest.runpod.io/v1"
DELETE_TIMEOUT = 120


def api_key():
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    return os.environ["RUNPOD_API_KEY"]


def request(method, url, key=None, **kwargs):
    headers = {"User-Agent": "Mozilla/5.0"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return httpx.request(method, url, headers=headers, timeout=30, **kwargs)


def delete_pod(pod_id, key):
    url = f"{API}/pods/{pod_id}"
    result = request("DELETE", url, key)
    if result.status_code != 404:
        result.raise_for_status()
    deadline = time.monotonic() + DELETE_TIMEOUT
    while time.monotonic() < deadline:
        result = request("GET", url, key)
        if result.status_code == 404:
            return
        result.raise_for_status()
        time.sleep(2)
    raise TimeoutError(f"Pod {pod_id} still exists after deletion")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pod_id")
    args = parser.parse_args(argv)
    delete_pod(args.pod_id, api_key())


if __name__ == "__main__":
    main()
