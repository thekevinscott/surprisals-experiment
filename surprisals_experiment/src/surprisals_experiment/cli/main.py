"""Argument parsing and presentation for the experiment SDK."""

import argparse
import asyncio
import signal
import sys
from functools import partial
from pathlib import Path
from typing import get_args

from dotenv import dotenv_values, find_dotenv

from surprisals_experiment.config import T_MODEL, U_MODEL, ThinkingLevel
from surprisals_experiment.sdk import Config, run_experiment


async def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="surprisals_experiment",
        description="Run the U → T experiment on an APPS problem.",
    )
    parser.add_argument("--u-mode", choices=("chat", "agent"), default="agent",
                        help="U interface (default: agent)")
    parser.add_argument("--u-compact-chars", type=int, default=400000,
                        help="Chat U conversation compaction threshold; 0 disables (default: 400000)")
    parser.add_argument("-U", default=U_MODEL, help="Advisor OpenRouter model ID")
    parser.add_argument("--u-thinking", choices=get_args(ThinkingLevel),
                        default="high", help="U thinking level (default: high)")
    parser.add_argument("-T", default=T_MODEL, help="Executor OpenRouter model ID")
    parser.add_argument("--t-samples", type=int, default=5,
                        help="Independent T solutions per advice; all must pass (default: 5)")
    parser.add_argument("--t-pool-size", type=int, default=3,
                        help="Maximum concurrent T generations (default: 3)")
    parser.add_argument("--t-sample-timeout", type=float, default=900,
                        help="Time limit per active T sample in seconds (default: 900)")
    parser.add_argument("--t-sample-retries", type=int, default=3,
                        help="Retries per timed-out T sample; 0 disables retries (default: 3)")
    parser.add_argument("--max-turns-without-improvement", type=int, default=20,
                        help="Stop after this many turns without shorter all-pass advice (default: 20)")
    parser.add_argument(
        "--max-u-turns", type=int, help="Optional total iteration limit (default: stop after no improvement or interruption)",
    )
    parser.add_argument("--output", type=Path, required=True, help="New directory to retain T’s solution")
    commands = parser.add_subparsers(dest="command", required=True)
    problem = commands.add_parser("problem", help="Select a problem directory")
    source = problem.add_mutually_exclusive_group(required=True)
    source.add_argument("problem_dir", nargs="?", type=Path, help="Directory containing question.txt and input_output.json")
    source.add_argument("--problem-dir", dest="problem_dir_option", type=Path, help="Problem directory (for parameter grids)")
    args = parser.parse_args(argv)
    active_section = None

    def print_delta(kind: str, text: str, *, agent: str = "U") -> None:
        nonlocal active_section
        destination = sys.stdout
        color_code = "\033[90m" if kind == "thinking" else "\033[34m"
        color = color_code if destination.isatty() else ""
        reset = "\033[0m" if color else ""
        if (agent, kind) != active_section:
            print(f"\n{color}[{agent} {kind}]{reset}", file=destination, flush=True)
            active_section = (agent, kind)
        print(f"{color}{text}{reset}", end="", file=destination, flush=True)

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, asyncio.current_task().cancel)
    try:
        env_file = find_dotenv(usecwd=True)
        if not env_file:
            raise ValueError("No .env found in the current directory or its parents")
        key = dotenv_values(env_file, interpolate=False).get("OPENROUTER_API_KEY")
        if not key or not key.strip():
            raise ValueError("Set OPENROUTER_API_KEY in your .env file")
        await run_experiment(Config(
            api_key=key,
            problem_dir=args.problem_dir or args.problem_dir_option,
            output=args.output,
            u_model=args.U,
            u_mode=args.u_mode,
            u_compact_chars=args.u_compact_chars,
            u_thinking=args.u_thinking,
            t_model=args.T,
            t_samples=args.t_samples,
            t_pool_size=args.t_pool_size,
            t_sample_timeout=args.t_sample_timeout,
            t_sample_retries=args.t_sample_retries,
            max_u_turns=args.max_u_turns,
            max_turns_without_improvement=args.max_turns_without_improvement,
        ), on_delta=print_delta, on_t_delta=partial(print_delta, agent="T"))
    except (ValueError, OSError, RuntimeError) as error:
        parser.error(str(error))
    finally:
        loop.remove_signal_handler(signal.SIGTERM)

    print()
