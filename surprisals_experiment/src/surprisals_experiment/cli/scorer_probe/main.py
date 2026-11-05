import argparse
import json
from pathlib import Path

from .probe import probe


async def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Probe the experiment's fixed RunPod scorer from any host.")
    parser.add_argument("endpoint", help="Scorer base URL, including /v1")
    parser.add_argument("prompt", type=Path, help="UTF-8 advice file to score repeatedly")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--requests", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        result = await probe(args.endpoint, args.prompt.read_bytes().decode("utf-8"),
                             concurrency=args.concurrency, requests=args.requests)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))
    if result["failed"]:
        raise SystemExit(1)
