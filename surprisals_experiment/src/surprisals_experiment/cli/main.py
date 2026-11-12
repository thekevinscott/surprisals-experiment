"""Argument parsing and presentation for the experiment SDK."""

import argparse
import asyncio
import signal
from pathlib import Path
from typing import get_args

import labnotes
from dotenv import dotenv_values, find_dotenv

from surprisals_experiment.config import (
    CAP_STRATEGY,
    FORK_TURNS,
    INFRA_RETRIES,
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
    WINDOW_FORKS,
    WINDOW_SOLO_TURNS,
    ThinkingLevel,
)
from surprisals_experiment.sdk import Config, run_experiment



async def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="surprisals_experiment",
        description="Run the U → T experiment on an APPS problem.",
    )
    parser.add_argument("-U", default=U_MODEL, help="Advisor OpenRouter model ID")
    parser.add_argument(
        "--u-provider", default=U_PROVIDER, help=f"OpenRouter provider U is pinned to (default: {U_PROVIDER})"
    )
    parser.add_argument(
        "--u-thinking",
        choices=get_args(ThinkingLevel),
        default=U_THINKING,
        help=f"U thinking level (default: {U_THINKING})",
    )
    parser.add_argument("-T", default=T_MODEL, help="Executor OpenRouter model ID")
    parser.add_argument(
        "--cap-strategy",
        choices=("characters", "surprisal"),
        default=CAP_STRATEGY,
        help=f"Advice cap strategy (default: {CAP_STRATEGY})",
    )
    parser.add_argument(
        "--scorer-base-url", help="OpenAI-compatible prompt-logprob endpoint"
    )
    parser.add_argument(
        "--t-samples",
        type=int,
        default=T_SAMPLES,
        help=f"Independent T solutions per advice; all must pass (default: {T_SAMPLES})",
    )
    parser.add_argument(
        "--t-pool-size",
        type=int,
        default=T_POOL_SIZE,
        help=f"Maximum concurrent T generations (default: {T_POOL_SIZE})",
    )
    parser.add_argument(
        "--t-sample-timeout",
        type=float,
        default=T_SAMPLE_TIMEOUT,
        help=f"Time limit per active T sample in seconds (default: {T_SAMPLE_TIMEOUT})",
    )
    parser.add_argument(
        "--t-sample-retries",
        type=int,
        default=T_SAMPLE_RETRIES,
        help=f"Retries per timed-out T sample; 0 disables retries (default: {T_SAMPLE_RETRIES})",
    )
    parser.add_argument(
        "--infra-retries",
        type=int,
        default=INFRA_RETRIES,
        help=f"Restarts of the whole run after a fatal error, 60s apart; 0 disables (default: {INFRA_RETRIES})",
    )
    parser.add_argument(
        "--max-u-turns",
        type=int,
        help="Optional per-fork iteration limit",
    )
    parser.add_argument(
        "--window-forks",
        type=int,
        default=WINDOW_FORKS,
        help=f"Parallel forks at the start of each window (default: {WINDOW_FORKS})",
    )
    parser.add_argument(
        "--fork-turns",
        type=int,
        default=FORK_TURNS,
        help=f"Turn target for the parallel fork round (default: {FORK_TURNS})",
    )
    parser.add_argument(
        "--window-solo-turns",
        type=int,
        default=WINDOW_SOLO_TURNS,
        help=f"Turns the winning fork continues alone after the fork round; its fork folder ends with fork-turns + window-solo-turns turns (default: {WINDOW_SOLO_TURNS})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New directory to retain T’s solution",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "problem_dir",
        nargs="?",
        type=Path,
        help="Directory containing question.txt and input_output.json",
    )
    source.add_argument(
        "--problem-dir",
        dest="problem_dir_option",
        type=Path,
        help="Problem directory (for parameter grids)",
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
        if args.cap_strategy == "surprisal" and not args.scorer_base_url:
            args.scorer_base_url = labnotes.get_state().get("base_url")
        await run_experiment(
            Config(
                api_key=key,
                problem_dir=args.problem_dir or args.problem_dir_option,
                output=args.output,
                u_model=args.U,
                u_thinking=args.u_thinking,
                u_provider=args.u_provider,
                t_model=args.T,
                t_provider=T_PROVIDERS[args.T],
                cap_strategy=args.cap_strategy,
                scorer_base_url=args.scorer_base_url,
                scorer_model=SCORER_MODEL,
                t_samples=args.t_samples,
                t_pool_size=args.t_pool_size,
                t_sample_timeout=args.t_sample_timeout,
                t_sample_retries=args.t_sample_retries,
                infra_retries=args.infra_retries,
                window_forks=args.window_forks,
                fork_turns=args.fork_turns,
                window_solo_turns=args.window_solo_turns,
                max_u_turns=args.max_u_turns,
            ),
            on_delta=None,
        )
    except (ValueError, OSError, RuntimeError) as error:
        parser.error(str(error))
    finally:
        loop.remove_signal_handler(signal.SIGTERM)

    print()
