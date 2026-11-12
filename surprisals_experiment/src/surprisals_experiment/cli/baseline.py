"""T on question.txt alone, for sorting problems into solvable and not."""

import argparse
import asyncio
import signal
from pathlib import Path

from dotenv import dotenv_values, find_dotenv

from surprisals_experiment.config import (
    SCORER_MODEL,
    T_MODEL,
    T_POOL_SIZE,
    T_PROVIDERS,
    T_SAMPLE_RETRIES,
    T_SAMPLE_TIMEOUT,
    T_SAMPLES,
    U_MODEL,
    U_PROVIDER,
    U_THINKING,
)
from surprisals_experiment.sdk import Config
from surprisals_experiment.sdk.run_baseline import run_baseline

from .print_delta import PrintDelta


async def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="surprisals_experiment.cli.baseline",
        description="Run T on an APPS problem's question.txt alone and test each sample.",
    )
    parser.add_argument("-T", default=T_MODEL, help="Executor OpenRouter model ID")
    parser.add_argument("--t-samples", type=int, default=T_SAMPLES, help=f"Independent T solutions (default: {T_SAMPLES})")
    parser.add_argument("--t-pool-size", type=int, default=T_POOL_SIZE, help=f"Maximum concurrent T generations (default: {T_POOL_SIZE})")
    parser.add_argument(
        "--t-sample-timeout", type=float, default=T_SAMPLE_TIMEOUT, help=f"Time limit per active T sample in seconds (default: {T_SAMPLE_TIMEOUT})"
    )
    parser.add_argument(
        "--t-sample-retries", type=int, default=T_SAMPLE_RETRIES,
        help=f"Retries per timed-out T sample; 0 disables retries (default: {T_SAMPLE_RETRIES})",
    )
    parser.add_argument("--output", type=Path, required=True, help="Run directory")
    parser.add_argument(
        "--problem-dir", type=Path, required=True, help="Directory containing question.txt and input_output.json"
    )
    args = parser.parse_args(argv)

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, asyncio.current_task().cancel)
    try:
        env_file = find_dotenv(usecwd=True)
        if not env_file:
            raise ValueError("No .env found in the current directory or its parents")
        key = dotenv_values(env_file, interpolate=False).get("OPENROUTER_API_KEY")
        if not key or not key.strip():
            raise ValueError("Set OPENROUTER_API_KEY in your .env file")
        await run_baseline(
            Config(
                api_key=key,
                problem_dir=args.problem_dir,
                output=args.output,
                u_model=U_MODEL,
                u_thinking=U_THINKING,
                u_provider=U_PROVIDER,
                t_model=args.T,
                t_provider=T_PROVIDERS[args.T],
                scorer_model=SCORER_MODEL,
                t_samples=args.t_samples,
                t_pool_size=args.t_pool_size,
                t_sample_timeout=args.t_sample_timeout,
                t_sample_retries=args.t_sample_retries,
            ),
            on_t_delta=PrintDelta(),
        )
    except (ValueError, OSError, RuntimeError) as error:
        parser.error(str(error))
    finally:
        loop.remove_signal_handler(signal.SIGTERM)


if __name__ == "__main__":
    asyncio.run(main())
