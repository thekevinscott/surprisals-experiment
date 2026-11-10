"""T on question.txt alone, for sorting problems into solvable and not."""

import argparse
import asyncio
import signal
from pathlib import Path

from dotenv import dotenv_values, find_dotenv

from surprisals_experiment.config import SCORER_MODEL, T_MODEL, T_PROVIDERS, U_MODEL, U_PROVIDER
from surprisals_experiment.sdk import Config
from surprisals_experiment.sdk.run_baseline import run_baseline

from .log_streams import LogStreams


async def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="surprisals_experiment.cli.baseline",
        description="Run T on an APPS problem's question.txt alone and test each sample.",
    )
    parser.add_argument("-T", default=T_MODEL, help="Executor OpenRouter model ID")
    parser.add_argument("--t-samples", type=int, default=5, help="Independent T solutions (default: 5)")
    parser.add_argument("--t-pool-size", type=int, default=3, help="Maximum concurrent T generations (default: 3)")
    parser.add_argument(
        "--t-sample-timeout", type=float, default=900, help="Time limit per active T sample in seconds (default: 900)"
    )
    parser.add_argument(
        "--t-sample-retries", type=int, default=3,
        help="Retries per timed-out T sample; 0 disables retries (default: 3)",
    )
    parser.add_argument("--output", type=Path, required=True, help="Run directory")
    parser.add_argument(
        "--problem-dir", type=Path, required=True, help="Directory containing question.txt and input_output.json"
    )
    args = parser.parse_args(argv)
    streams = LogStreams()

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
                u_thinking="high",
                u_provider=U_PROVIDER,
                t_model=args.T,
                t_provider=T_PROVIDERS[args.T],
                scorer_model=SCORER_MODEL,
                t_samples=args.t_samples,
                t_pool_size=args.t_pool_size,
                t_sample_timeout=args.t_sample_timeout,
                t_sample_retries=args.t_sample_retries,
            ),
            on_t_delta=streams.delta,
        )
    except (ValueError, OSError, RuntimeError) as error:
        parser.error(str(error))
    finally:
        streams.close()
        loop.remove_signal_handler(signal.SIGTERM)


if __name__ == "__main__":
    asyncio.run(main())
