import time

import httpx

from .timestamp import timestamp

API = "https://api.runpod.io/v2"
READ_SECONDS = 30


def save_logs(pod_id, key, folder):
    path = folder / "runpod-logs.jsonl"
    deadline = time.monotonic() + READ_SECONDS
    try:
        # The endpoint is an SSE stream that never closes on its own.
        with httpx.stream(
            "GET",
            f"{API}/pods/{pod_id}/logs",
            params={"tail": 5000},
            headers={"User-Agent": "Mozilla/5.0", "Authorization": f"Bearer {key}"},
            timeout=httpx.Timeout(30, read=10),
        ) as response:
            response.raise_for_status()
            with path.open("w") as file:
                for line in response.iter_lines():
                    if line.startswith("data:"):
                        file.write(line.removeprefix("data:").strip() + "\n")
                    if time.monotonic() > deadline:
                        break
    except httpx.ReadTimeout:
        pass
    except (httpx.HTTPError, OSError) as error:
        timestamp(f"Pod {pod_id} logs not saved: {error!r}")
        return
    timestamp(f"Saved pod {pod_id} logs to {path}")
