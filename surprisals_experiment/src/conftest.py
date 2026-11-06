"""Script Botbox, U and the scorer for unit tests; keep orchestration and evaluation real."""

import asyncio
import json
import shlex
from collections import deque
from inspect import signature
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from botbox import Botbox
from fake_botbox import FakeSession, Script


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


@pytest.fixture(autouse=True)
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
