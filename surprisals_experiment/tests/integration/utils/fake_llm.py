"""Fakes U and T from a world (see world.py), pausing the run after each reply to check its state."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import httpx2
from botbox import RunResult
from openai import AsyncOpenAI
from surprisals_experiment.sdk.run_test_suite import TestResult

from utils.expected import decoded, masked
from utils.run_files import run_files
from utils.world import REMOVED, U, Done, State, T


class FakeLLM:
    def __init__(self, world, output):
        self.states = [state for state in world if isinstance(state, State)]
        self.done = world[-1] if isinstance(world[-1], Done) else None
        self.output = output
        self.asked = 0
        self.arrived = [asyncio.get_running_loop().create_future() for _ in self.states]
        self.target = 0
        self.advance = asyncio.Event()
        self.events = []
        self.seen = 0
        self.files = run_files(output)
        self.boxes = []
        self.failure = None
        self.killed = False
        self.followers = {}

    def __enter__(self):
        self.patches = [
            patch('surprisals_experiment.sdk.utils.botbox_run.botbox_run.Botbox', self.botbox),
            patch('surprisals_experiment.sdk.utils.botbox_run.botbox_run.follow', self.follow),
            patch('surprisals_experiment.sdk.run_test_suite.run_test_suite_for_t.run_case', self.run_case),
            patch('surprisals_experiment.sdk.utils.u_chat.opener.AsyncOpenAI', self.openai),
        ]
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *args):
        for p in self.patches:
            p.stop()

    async def reached(self, state):
        """Let the run go on to `state`, and wait until that state has been checked."""
        index = self.states.index(state)
        self.target = max(self.target, index)
        self.advance.set()
        await self.arrived[index]

    def kill(self):
        self.killed = True
        self.task.cancel()

    def release(self):
        self.target = len(self.states)
        self.advance.set()

    def log(self, *event):
        self.events.append(event)

    def ended(self, task):
        outcome = 'cancelled' if task.cancelled() else task.exception() or task.result()
        for index, future in enumerate(self.arrived):
            if not future.done():
                future.set_exception(self.failure or AssertionError(f'Run ended ({outcome!r}) before state {index}'))

    def check(self, name, expected):
        assert self.events[self.seen:] == expected.logs, f'{name} logs'
        self.seen = len(self.events)
        now = run_files(self.output)
        changed = {path: content for path, content in now.items() if self.files.get(path) != content}
        changed |= {path: REMOVED for path in self.files.keys() - now.keys()}
        self.files = now
        assert {path: decoded(expected.files[path], content) if path in expected.files else content
                for path, content in changed.items()} == expected.files, f'{name} files'

    async def checked(self, check, *args):
        """Run a check inside the run; a failure stops the run instead of reaching its error handling."""
        try:
            return check(*args)
        except AssertionError as error:
            self.failure = error
            self.task.cancel()
            await asyncio.Future()

    def ask(self, kind, sent):
        index = self.asked
        assert index < len(self.states), f'{kind.__name__} was asked with no reply left: {sent!r:.300}'
        state = self.states[index]
        assert isinstance(state.reply, kind), \
            f'{kind.__name__} was asked, but state {index} is {type(state.reply).__name__}'
        assert masked(state.sent, sent) == state.sent, f'state {index} sent'
        self.asked += 1
        return index, state.reply

    async def follow(self, path, on_event):
        self.followers[path] = on_event
        await asyncio.Future()

    def say(self, stdout, kind, delta):
        """Append one pi stdout event, as T's container writes it, and hand it to follow()."""
        event = {'type': 'message_update', 'assistantMessageEvent': {'type': kind, 'delta': delta}}
        with stdout.open('a') as file:
            file.write(json.dumps(event) + '\n')
        self.followers[stdout](event)

    async def delivered(self, index):
        await self.checked(self.check, f'state {index}', self.states[index])
        self.arrived[index].set_result(None)
        while index >= self.target:
            self.advance.clear()
            await self.advance.wait()

    def openai(self, **kwargs):
        async def respond(request):
            body = json.loads(request.content)
            index, reply = await self.checked(self.ask, U, body)
            deltas = [({'reasoning': reply.thinking}, None), ({'content': reply.text}, 'stop')]
            chunks = [{'id': 'u', 'object': 'chat.completion.chunk', 'created': 1, 'model': body['model'],
                       'choices': [{'index': 0, 'delta': {'role': 'assistant', **delta},
                                    'finish_reason': finish}]}
                      for delta, finish in deltas]

            async def stream():
                for chunk in chunks:
                    yield f'data: {json.dumps(chunk)}\n\n'.encode()
                await self.delivered(index)
                yield b'data: [DONE]\n\n'

            return httpx2.Response(200, headers={'content-type': 'text/event-stream'}, content=stream())

        return AsyncOpenAI(**kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)))

    async def run_case(self, index, stdin, expected, solution_dir, timeout_seconds):
        # Blocking: under looptime, awaiting a real subprocess jumps virtual time to the case timeout.
        process = subprocess.run([sys.executable, 'main.py'], cwd=solution_dir, input=stdin,
                                 capture_output=True, text=True)
        passed = process.returncode == 0 and process.stdout.strip() == expected.strip()
        status = 'passed' if passed else 'runtime_error' if process.returncode else 'wrong_answer'
        return TestResult(index, passed, status, process.stdout, process.stderr, process.returncode)

    @property
    def botbox(self):
        llm = self

        class Botbox:
            def __init__(self, agent, *, dockerfile):
                pass

            async def __aenter__(self):
                self.exited = False
                llm.boxes.append(self)
                return self

            async def __aexit__(self, *args):
                self.exited = True

            async def build(self):
                return 'fake'

            async def run(self, command, *, mounts, workdir, output):
                mounted = {target: Path(source) for source, target, _ in mounts}
                attempt = Path(output).relative_to(llm.output).as_posix()
                index, t = await llm.checked(llm.ask, T, (attempt, (mounted['/advice'] / 'advice.md').read_text()))
                await asyncio.sleep(t.seconds)
                stdout = Path(output) / 'stdout.txt'
                stdout.parent.mkdir(parents=True, exist_ok=True)
                if t.thinking is not None:
                    llm.say(stdout, 'thinking_delta', t.thinking)
                for name, content in t.files.items():
                    (mounted['/solution'] / name).write_text(content)
                if t.text is not None:
                    llm.say(stdout, 'text_delta', t.text)
                await llm.delivered(index)
                if t.error:
                    raise t.error
                if t.hang:
                    await asyncio.Future()
                return RunResult(exit_code=t.exit_code)

        return Botbox
