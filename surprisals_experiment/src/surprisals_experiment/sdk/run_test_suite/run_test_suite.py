"""Run cases one at a time and persist their output without retaining a case list."""

import json
import shutil
import time
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryFile
from textwrap import indent

from surprisals_experiment.config import TEST_TIMEOUT_SECONDS

from .run_case import run_case


async def run_test_suite(test_suite: dict, solution_dir: Path) -> Path:
    """Write tests.json and return its path; case output stays on disk."""
    started = time.monotonic()
    passed = total = 0
    # Stage serialized cases on disk so the summary can precede them in tests.json.
    with TemporaryFile(mode="w+", encoding="utf-8") as cases:
        for index, (stdin, expected) in enumerate(zip(test_suite["inputs"], test_suite["outputs"], strict=True)):
            case = await run_case(index, stdin, expected, solution_dir, TEST_TIMEOUT_SECONDS)
            if total:
                cases.write(",\n")
            cases.write(indent(json.dumps(asdict(case), indent=2), "    "))
            passed += case.passed
            total += 1
            del case
        summary = json.dumps({
            "duration_seconds": round(time.monotonic() - started, 3),
            "passed": passed,
            "failed": total - passed,
            "total": total,
            "all_passed": total > 0 and passed == total,
        }, indent=2)
        path = solution_dir.parent / "tests.json"
        with path.open("w") as output:
            output.write(summary[:-2] + ',\n  "cases": [')
            if total:
                output.write("\n")
                cases.seek(0)
                shutil.copyfileobj(cases, output, length=65536)
                output.write("\n  ")
            output.write("]\n}\n")
    return path
