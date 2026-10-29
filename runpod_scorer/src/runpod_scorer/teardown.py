"""Delete a scorer and verify it is gone."""

import os
import time
from pathlib import Path

import httpx
import labnotes
from dotenv import load_dotenv

API = "https://rest.runpod.io/v1"
DELETE_TIMEOUT = 120


def api_key():
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    return os.environ["RUNPOD_API_KEY"]


def request(method, url, key=None, **kwargs):
    # Cloudflare returns 403 without a browser User-Agent.
    headers = {"User-Agent": "Mozilla/5.0"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return httpx.request(method, url, headers=headers, timeout=30, **kwargs)


def delete_pod(pod_id, key):
    url = f"{API}/pods/{pod_id}"
    for attempt in range(3):
        result = request("DELETE", url, key)
        if result.status_code < 500 or attempt == 2:
            break
        time.sleep(attempt + 1)
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


def down():
    pod_id = labnotes.get_state().get("pod_id")
    if pod_id:
        delete_pod(pod_id, api_key())
