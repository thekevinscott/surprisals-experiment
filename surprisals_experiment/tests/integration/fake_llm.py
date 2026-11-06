"""A fake LLM for U and T whose replies are laid out like the run folder.

Run(Window(Fork(Turn(U('advice'), T(files), ...)))): the turn at Run[w][f][n] answers for
windows/w/forks/f/turns/n, and its n-th T for ts/n. U calls take the next unanswered turn in
tree order. KILL cancels the run the first time it is reached.
"""

import asyncio
import json
import re
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import httpx2
import pytest
from botbox import RunResult
from openai import AsyncOpenAI

KILL = object()


class Node(tuple):
    def __new__(cls, *children):
        return super().__new__(cls, children)


class Run(Node):
    pass


class Window(Node):
    pass


class Fork(Node):
    pass


class Turn:
    def __init__(self, u, *ts):
        self.u = u
        self.ts = ts


class U:
    def __init__(self, text):
        self.text = text


class T:
    """Steps in order: a dict of files to write, or KILL. T finishes after the last step."""

    def __init__(self, *steps):
        self.steps = steps


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
