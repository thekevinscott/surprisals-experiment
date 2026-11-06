"""Fakes U and T together; see llm_replies for the reply layout."""

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

SAMPLE = re.compile(r'windows/(\d+)/forks/(\d+)/turns/(\d+)/ts/(\d+)(?:/attempts/\d+)?$')


def say(stdout, kind, delta):
    """Append one pi stdout event, as T's container writes it."""
    event = {'type': 'message_update', 'assistantMessageEvent': {'type': kind, 'delta': delta}}
    with stdout.open('a') as file:
        file.write(json.dumps(event) + '\n')


class FakeLLM:
    def __init__(self, run):
        self.turns = [turn for window in run for fork in window for turn in fork]
        self.unasked = list(self.turns)
        self.kill_target = None
        self.samples = {
            (w, f, n, s): list(sample)
            for w, window in enumerate(run)
            for f, fork in enumerate(window)
            for n, turn in enumerate(fork)
            for s, sample in enumerate(turn.samples)
        }

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
        return len(self.unasked) + sum(len(sample) for sample in self.samples.values())

    @contextmanager
    def killed(self):
        with pytest.raises(asyncio.CancelledError):
            yield
        self.task.uncancel()

    def kill_after(self, reply):
        """Cancel the run once T has written this reply's files, before T finishes."""
        self.kill_target = reply

    def openai(self, **kwargs):
        async def respond(request):
            body = json.loads(request.content)
            assert self.unasked, f'U was asked with no turn left: {body["messages"][-1]!r:.200}'
            reply = self.unasked.pop(0).u
            deltas = [({'reasoning': reply.thinking}, None), ({'content': reply.text}, 'stop')]
            chunks = [{'id': 'u', 'object': 'chat.completion.chunk', 'created': 1, 'model': body['model'],
                       'choices': [{'index': 0, 'delta': {'role': 'assistant', **delta},
                                    'finish_reason': finish}]}
                      for delta, finish in deltas]
            stream = ''.join(f'data: {json.dumps(chunk)}\n\n' for chunk in chunks)
            return httpx2.Response(200, headers={'content-type': 'text/event-stream'},
                                   content=stream + 'data: [DONE]\n\n')

        return AsyncOpenAI(**kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)))

    def t(self, output):
        match = SAMPLE.search(Path(output).as_posix())
        assert match, f'T ran outside a sample folder: {output}'
        sample = self.samples.get(tuple(map(int, match.groups())))
        assert sample, f'No T reply left for {match.group(0)}'
        return sample.pop(0)

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
                stdout = Path(output) / 'stdout.txt'
                stdout.parent.mkdir(parents=True, exist_ok=True)
                say(stdout, 'thinking_delta', t.thinking)
                for name, content in t.files.items():
                    (solution / name).write_text(content)
                if t is llm.kill_target:
                    llm.kill_target = None
                    llm.task.cancel()
                    await asyncio.Future()
                say(stdout, 'text_delta', t.text)
                return RunResult(exit_code=0)

        return Botbox
