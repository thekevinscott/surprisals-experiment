"""Run one stdin/stdout test case."""

import asyncio
import contextlib
import os
import shutil
import signal
import sys
import tempfile
from pathlib import Path

from .results import TestResult

OUTPUT_MARGIN_BYTES = 1 << 20


async def run_case(index: int, stdin: str, expected: str, solution_dir: Path, timeout_seconds: float) -> TestResult:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as sandbox:
        shutil.copytree(solution_dir, Path(sandbox) / "src")
        process = await asyncio.create_subprocess_exec(
            sys.executable, "main.py", cwd=Path(sandbox) / "src", env={},
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        limit = len(expected.encode()) + OUTPUT_MARGIN_BYTES

        async def feed() -> None:
            try:
                process.stdin.write(stdin.encode())
                await process.stdin.drain()
                process.stdin.close()
            except (BrokenPipeError, ConnectionResetError):
                pass

        async def read(stream: asyncio.StreamReader) -> bytes:
            data = bytearray()
            while len(data) <= limit and (chunk := await stream.read(1 << 16)):
                data += chunk
            if len(data) > limit:
                process.kill()
            return bytes(data)

        try:
            async with asyncio.timeout(timeout_seconds):
                _, stdout, stderr = await asyncio.gather(feed(), read(process.stdout), read(process.stderr))
                await process.wait()
            if max(len(stdout), len(stderr)) > limit:
                return TestResult(index, False, "error", "", f"Test output exceeded {limit} bytes", None)
            # Match subprocess text mode's universal newline handling.
            stdout = stdout.decode().replace("\r\n", "\n").replace("\r", "\n")
            stderr = stderr.decode().replace("\r\n", "\n").replace("\r", "\n")
            passed = process.returncode == 0 and stdout.strip() == expected.strip()
            status = "passed" if passed else "runtime_error" if process.returncode else "wrong_answer"
            return TestResult(index, passed, status, stdout, stderr, process.returncode)
        except TimeoutError:
            return TestResult(index, False, "error", "", f"Test exceeded {timeout_seconds} seconds", None)
        except UnicodeDecodeError as error:
            return TestResult(index, False, "error", "", str(error), None)
        finally:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            await process.communicate()
