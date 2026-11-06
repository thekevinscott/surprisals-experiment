"""Run one stdin/stdout test case."""

import asyncio
import sys
from pathlib import Path

from .results import TestResult

OUTPUT_MARGIN_BYTES = 1 << 20


class OutputLimitExceeded(Exception):
    pass


async def _feed(stream: asyncio.StreamWriter, data: bytes) -> None:
    try:
        stream.write(data)
        await stream.drain()
        stream.close()
    except (BrokenPipeError, ConnectionResetError):
        pass


async def _read(stream: asyncio.StreamReader, limit: int) -> bytes:
    data = bytearray()
    while chunk := await stream.read(1 << 16):
        data += chunk
        if len(data) > limit:
            raise OutputLimitExceeded
    return bytes(data)


async def _communicate(process: asyncio.subprocess.Process, stdin: bytes, limit: int) -> tuple[bytes, bytes]:
    try:
        async with asyncio.TaskGroup() as group:
            group.create_task(_feed(process.stdin, stdin))
            stdout = group.create_task(_read(process.stdout, limit))
            stderr = group.create_task(_read(process.stderr, limit))
    except* OutputLimitExceeded:
        raise OutputLimitExceeded from None
    await process.wait()
    return stdout.result(), stderr.result()


async def run_case(index: int, stdin: str, expected: str, solution_dir: Path, timeout_seconds: float) -> TestResult:
    process = await asyncio.create_subprocess_exec(
        sys.executable, "main.py", cwd=solution_dir,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    limit = len(expected.encode()) + OUTPUT_MARGIN_BYTES
    try:
        async with asyncio.timeout(timeout_seconds):
            stdout, stderr = await _communicate(process, stdin.encode(), limit)
        # Match subprocess text mode's universal newline handling.
        stdout = stdout.decode().replace("\r\n", "\n").replace("\r", "\n")
        stderr = stderr.decode().replace("\r\n", "\n").replace("\r", "\n")
        passed = process.returncode == 0 and stdout.strip() == expected.strip()
        status = "passed" if passed else "runtime_error" if process.returncode else "wrong_answer"
        return TestResult(index, passed, status, stdout, stderr, process.returncode)
    except TimeoutError:
        return TestResult(index, False, "error", "", f"Test exceeded {timeout_seconds} seconds", None)
    except OutputLimitExceeded:
        return TestResult(index, False, "error", "", f"Test output exceeded {limit} bytes", None)
    except UnicodeDecodeError as error:
        return TestResult(index, False, "error", "", str(error), None)
    finally:
        if process.returncode is None:
            process.kill()
        await process.communicate()
