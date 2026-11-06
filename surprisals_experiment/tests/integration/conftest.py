"""Script Botbox runs globally; keep orchestration and evaluation real."""

import asyncio
import json
import re
import shlex
from collections import deque
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from inspect import signature
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx2
import pytest
from botbox import Botbox, RunResult
from llm_replies import KILL
from openai import AsyncOpenAI
from surprisals_experiment.config import Config


@dataclass
class Script:
    advice: deque = field(default_factory=deque)
    solutions: deque = field(default_factory=deque)
    sessions: list = field(default_factory=list)
    commands: list = field(default_factory=list)


class FakeSession:
    def __init__(self, agent, mounts, output, script):
        self.agent = agent
        self.output = Path(output)
        self.mounts = {target: Path(source) for source, target, _ in mounts}
        self.script = script
        self.messages = []
        self.closed = False
        self.result = None
        script.sessions.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.result = self.close()

    async def message(self, text):
        self.messages.append(text)
        reply = self.script.solutions.popleft()
        if isinstance(reply, Exception):
            raise reply
        (self.mounts["/solution"] / "main.py").write_text(reply)
        events = [
            {
                "type": "agent_end",
                "willRetry": False,
                "messages": [
                    {
                        "role": "assistant",
                        "stopReason": "stop",
                        "content": [{"type": "text", "text": "Solution written."}],
                    }
                ],
            },
            {"type": "agent_settled", "aborted": False},
        ]
        with (self.output / "stdout.txt").open("a") as stdout:
            stdout.writelines(json.dumps(event) + "\n" for event in events)

    def close(self):
        self.closed = True
        (self.output / "transcripts").mkdir(parents=True, exist_ok=True)
        (self.output / "transcripts/session.jsonl").write_text(
            "\n".join(json.dumps({"prompt": text}) for text in self.messages)
        )
        for name in ("stderr.txt", "proxy.log"):
            (self.output / name).write_text("")
        return RunResult(exit_code=0)


@pytest.fixture(autouse=True)
def botbox_script():
    script = Script()

    class FakeBotbox:
        def __init__(self, agent, *, dockerfile):
            signature(Botbox).bind(agent, dockerfile=dockerfile)
            self.agent = agent

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def build(self):
            return "fake"

        async def run(self, command, *, mounts, workdir, output):
            script.commands.append(command)
            args = shlex.split(command)
            assert args[args.index("-p") + 1] == "@/advice/advice.md"
            advice_dir = next(
                Path(source)
                for source, target, mode in mounts
                if target == "/advice" and mode == "ro"
            )
            assert workdir == "/solution"
            Path(output).mkdir(parents=True, exist_ok=True)
            (Path(output) / "stdout.txt").write_text("")
            async with FakeSession(self.agent, mounts, output, script) as session:
                await session.message(
                    (advice_dir / "advice.md").read_bytes().decode("utf-8")
                )
            return session.result

    with patch(
        "surprisals_experiment.sdk.utils.botbox_run.botbox_run.Botbox", FakeBotbox
    ):
        yield script


@pytest.fixture
def no_retry_wait(monkeypatch):
    waits = AsyncMock()
    real_sleep = asyncio.sleep

    # Retry waits are 10 s and up; shorter sleeps are polls that must yield.
    async def sleep(delay, *args, **kwargs):
        if delay >= 1:
            return await waits(delay)
        return await real_sleep(delay, *args, **kwargs)

    monkeypatch.setattr(asyncio, "sleep", sleep)
    return waits


@pytest.fixture
def config(tmp_path):
    problem = tmp_path / "problem"
    problem.mkdir()
    (problem / "question.txt").write_text("Read an integer and print its double.")
    (problem / "input_output.json").write_text(
        json.dumps(
            {
                "inputs": ["3\n", "7\n"],
                "outputs": ["6\n", "14\n"],
            }
        )
    )
    return Config(
        api_key="test-key",
        problem_dir=problem,
        output=tmp_path / "run",
        u_model="u",
        t_model="t",
        t_samples=1,
        u_thinking="high",
        max_u_turns=1,
        window_forks=1,
    )


@pytest.fixture(autouse=True)
def chat_provider(botbox_script):
    """Mock only HTTP; exercise the real SDK's streaming and message assembly."""
    import httpx2
    from openai import AsyncOpenAI

    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        reply = botbox_script.advice.popleft()
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, dict):
            status = reply.get("status", 200)
            if status != 200:
                return httpx2.Response(
                    status, json={"error": {"message": "provider failed"}}
                )
            deltas = reply["deltas"]
            finish = reply.get("finish", "stop")
        else:
            deltas = [
                {"role": "assistant", "reasoning": "Thinking."},
                {"role": "assistant", "content": reply[:2]},
                {"role": "assistant", "content": reply[2:]},
            ]
            finish = "stop"
        chunks = [
            {
                "id": "test-chat",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "u",
                "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
            }
            for delta in deltas
        ]
        if finish is not None:
            chunks.append(
                {
                    "id": "test-chat",
                    "object": "chat.completion.chunk",
                    "created": 1,
                    "model": "u",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": finish,
                            **(
                                reply.get("finish_choice", {})
                                if isinstance(reply, dict)
                                else {}
                            ),
                        }
                    ],
                }
            )
        if isinstance(reply, dict) and "usage" in reply:
            chunks.append(
                {
                    "id": "test-chat",
                    "object": "chat.completion.chunk",
                    "created": 1,
                    "model": "u",
                    "choices": [],
                    "usage": reply["usage"],
                }
            )
        if isinstance(reply, dict) and "stream_error" in reply:
            chunks.append({"error": reply["stream_error"]})
        stream = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
        if isinstance(reply, dict) and reply.get("drop_stream"):

            class DroppedStream(httpx2.AsyncByteStream):
                async def __aiter__(self):
                    yield stream.encode()
                    raise httpx2.RemoteProtocolError("stream disconnected")

            return httpx2.Response(
                200,
                headers={"content-type": "text/event-stream"},
                stream=DroppedStream(),
            )
        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=stream + "data: [DONE]\n\n",
        )

    def client(**kwargs):
        kwargs.setdefault("max_retries", 0)
        return AsyncOpenAI(
            **kwargs,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        )

    with patch("surprisals_experiment.sdk.utils.u_chat.opener.AsyncOpenAI", client):
        yield requests


@pytest.fixture
async def scorer_provider():
    """Serve prompt logprobs over mocked HTTP, keeping measurement and retries real."""
    import math
    from types import SimpleNamespace

    import httpx2
    from openai import AsyncOpenAI

    script = SimpleNamespace(replies=deque(), requests=[])
    clients = []

    def respond(request):
        body = json.loads(request.content)
        script.requests.append(body)
        reply = script.replies.popleft()
        if callable(reply):
            reply = reply(request)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, httpx2.Response):
            return reply
        tokens, bits = zip(*reply)
        offsets = []
        offset = 0
        for token in tokens:
            offsets.append(offset)
            offset += len(token)
        return httpx2.Response(
            200,
            json={
                "id": "score",
                "object": "text_completion",
                "created": 1,
                "model": body["model"],
                "choices": [
                    {
                        "index": 0,
                        "text": "",
                        "finish_reason": "stop",
                        "logprobs": {
                            "tokens": tokens,
                            "token_logprobs": [-value * math.log(2) for value in bits],
                            "text_offset": offsets,
                        },
                    }
                ],
            },
        )

    def client(**kwargs):
        http = httpx2.AsyncClient(transport=httpx2.MockTransport(respond))
        clients.append(http)
        return AsyncOpenAI(**kwargs, http_client=http)

    with patch("measure_surprisal.utils.client.AsyncOpenAI", client):
        yield script
    for client in clients:
        await client.aclose()


SAMPLE = re.compile(r'windows/(\d+)/forks/(\d+)/turns/(\d+)/ts/(\d+)(?:/attempts/\d+)?$')


class FakeLLM:
    def __init__(self, run):
        self.turns = [turn for window in run for fork in window for turn in fork]
        self.unasked = list(self.turns)
        self.run = run
        self.killed_at = set()
        self.unused = {id(t) for turn in self.turns for t in turn.ts}

    def __enter__(self):
        self.task = asyncio.current_task()
        self.patches = [
            patch('surprisals_experiment.sdk.utils.botbox_run.botbox_run.Botbox', self.botbox),
            patch('surprisals_experiment.sdk.utils.u_chat.opener.AsyncOpenAI', self.openai),
        ]
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *args):
        for p in self.patches:
            p.stop()

    @property
    def unused_replies(self):
        return len(self.unasked) + len(self.unused)

    @contextmanager
    def killed(self):
        with pytest.raises(asyncio.CancelledError):
            yield
        self.task.uncancel()

    async def kill(self, step):
        if id(step) in self.killed_at:
            return
        self.killed_at.add(id(step))
        self.task.cancel()
        await asyncio.Future()

    def openai(self, **kwargs):
        async def respond(request):
            body = json.loads(request.content)
            assert self.unasked, f'U was asked with no turn left: {body["messages"][-1]!r:.200}'
            reply = self.unasked.pop(0).u
            chunk = {'id': 'u', 'object': 'chat.completion.chunk', 'created': 1, 'model': body['model'],
                     'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': reply.text},
                                  'finish_reason': 'stop'}]}
            return httpx2.Response(200, headers={'content-type': 'text/event-stream'},
                                   content=f'data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n')

        return AsyncOpenAI(**kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)))

    def t(self, output):
        match = SAMPLE.search(Path(output).as_posix())
        assert match, f'T ran outside a sample folder: {output}'
        w, f, n, s = map(int, match.groups())
        try:
            return self.run[w][f][n].ts[s]
        except IndexError:
            raise AssertionError(f'No T reply for {match.group(0)}') from None

    @property
    def botbox(self):
        llm = self

        class Botbox:
            def __init__(self, agent, *, dockerfile):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def build(self):
                return 'fake'

            async def run(self, command, *, mounts, workdir, output):
                solution = next(Path(source) for source, target, _ in mounts if target == '/solution')
                t = llm.t(output)
                llm.unused.discard(id(t))
                for step in t.steps:
                    if step is KILL:
                        await llm.kill(step)
                    else:
                        for name, content in step.items():
                            (solution / name).write_text(content)
                Path(output).mkdir(parents=True, exist_ok=True)
                return RunResult(exit_code=0)

        return Botbox


@pytest.fixture
def fake_llm(no_retry_wait):
    with ExitStack() as stack:
        yield lambda run: stack.enter_context(FakeLLM(run))
