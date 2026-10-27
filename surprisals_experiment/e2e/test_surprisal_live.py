"""Opt-in paid RunPod check; never part of the default test suite or CI.

RUNPOD_E2E=1 RUNPOD_SCRIPTS=/path/to/scripts/runpod \
RUNPOD_ADVICE_ROOT=/path/to/runs/sanity-check \
uv run pytest -s e2e/test_surprisal_live.py
"""

import asyncio
import json
import math
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import pytest
from dotenv import dotenv_values

from surprisals_experiment.sdk.advice_measure import AdviceMeasure

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def advice_paths():
    root = Path(os.environ.get("RUNPOD_ADVICE_ROOT", REPO / "runs/sanity-check"))
    paths = sorted(root.glob("**/attempts/*/advices/*/advice.txt"))[:3]
    if len(paths) < 3:
        pytest.skip("needs three saved advice strings under RUNPOD_ADVICE_ROOT")
    return paths


@pytest.fixture
def runpod_scorer(advice_paths):
    if os.environ.get("RUNPOD_E2E") != "1":
        pytest.skip("set RUNPOD_E2E=1 to authorize one paid RunPod pod")
    scripts = Path(os.environ.get("RUNPOD_SCRIPTS", REPO / "scripts/runpod"))
    assert (scripts / "setup.py").exists(), "Set RUNPOD_SCRIPTS to the RunPod scripts checkout"
    key = dotenv_values(scripts.resolve().parents[1] / ".env").get("RUNPOD_API_KEY")
    assert key, "needs RUNPOD_API_KEY in the scripts repository's .env"

    def pod_ids():
        request = Request("https://rest.runpod.io/v1/pods",
                          headers={"Authorization": f"Bearer {key}", "User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=30) as response:
            return [pod["id"] for pod in json.load(response)]

    before = pod_ids()
    started = time.monotonic()
    print(json.dumps({"event": "starting", "at": datetime.now(timezone.utc).isoformat()}), flush=True)
    created = subprocess.run(
        ["uv", "run", str(scripts / "setup.py"), "--model", "openai/gpt-oss-120b",
         "--gpu", "NVIDIA H100 80GB HBM3"],
        capture_output=True, text=True, timeout=2100, check=False,
    )
    if created.returncode:
        pytest.fail(f"RunPod setup failed:\n{created.stderr}")
    pod = json.loads(created.stdout)
    try:
        print(json.dumps({"event": "ready", **pod,
                          "elapsed_seconds": time.monotonic() - started}), flush=True)
        yield pod
    finally:
        subprocess.run(["uv", "run", str(scripts / "teardown.py"), pod["pod_id"]],
                       check=True, timeout=180)
        remaining = pod_ids()
        assert pod["pod_id"] not in remaining
        print(json.dumps({"event": "deleted", "pod_id": pod["pod_id"],
                          "elapsed_seconds": time.monotonic() - started,
                          "at": datetime.now(timezone.utc).isoformat(),
                          "remaining_ids": remaining, "original_ids": before}), flush=True)


async def test_saved_advice_scores_on_real_scorer(runpod_scorer, advice_paths):
    measure = AdviceMeasure("surprisal", base_url=runpod_scorer["base_url"],
                            model="openai/gpt-oss-120b")
    scores = []
    async with asyncio.timeout(600):
        for path in advice_paths:
            advice = path.read_text()
            bits = await measure.score(advice)
            assert math.isfinite(bits) and bits > 0
            scores.append(bits)
            print(json.dumps({"event": "score", "source": str(path),
                              "characters": len(advice), "bits": bits}), flush=True)
    assert len(scores) == len(advice_paths)
