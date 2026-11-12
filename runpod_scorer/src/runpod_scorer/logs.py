import asyncio
import json
import time
from contextlib import asynccontextmanager

import httpx

from .timestamp import timestamp

API = "https://api.runpod.io/v2"
READ_SECONDS = 30


@asynccontextmanager
async def read_logs(pod_id, key, read_timeout=10):
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "GET",
            f"{API}/pods/{pod_id}/logs",
            params={"tail": 5000},
            headers={"User-Agent": "Mozilla/5.0", "Authorization": f"Bearer {key}"},
            timeout=httpx.Timeout(30, read=read_timeout),
        ) as response:
            response.raise_for_status()
            yield response


async def stream_logs(pod_id, key):
    try:
        async with read_logs(pod_id, key, read_timeout=None) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    entry = json.loads(line.removeprefix("data:").strip())
                    if entry.get("source") == "container":
                        timestamp(f"Pod {pod_id} log: {entry['line']}")
    except (httpx.HTTPError, OSError, ValueError, KeyError) as error:
        timestamp(f"Pod {pod_id} log stream failed: {error!r}")


async def write_logs(pod_id, key, path, deadline):
    async with read_logs(pod_id, key) as response:
        with path.open("w") as file:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    file.write(line.removeprefix("data:").strip() + "\n")
                if time.monotonic() > deadline:
                    break


def save_logs(pod_id, key, folder):
    path = folder / "runpod-logs.jsonl"
    deadline = time.monotonic() + READ_SECONDS
    try:
        asyncio.run(write_logs(pod_id, key, path, deadline))
    except httpx.ReadTimeout:
        pass
    except (httpx.HTTPError, OSError) as error:
        timestamp(f"Pod {pod_id} logs not saved: {error!r}")
        return
    timestamp(f"Saved pod {pod_id} logs to {path}")
