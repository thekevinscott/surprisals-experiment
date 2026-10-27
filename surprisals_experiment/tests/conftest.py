"""Script Botbox sessions globally; keep orchestration and evaluation real."""

import importlib
import json
from inspect import signature
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from botbox import Botbox, RunResult

from surprisals_experiment.config import Config
from surprisals_experiment.sdk.utils.u_agent import UAgent


@dataclass
class Script:
    advice: deque = field(default_factory=deque)
    solutions: deque = field(default_factory=deque)
    sessions: list = field(default_factory=list)
    snapshots: list = field(default_factory=list)

    @property
    def u_sessions(self):
        return [session for session in self.sessions if session.is_u]

    @property
    def t_sessions(self):
        return [session for session in self.sessions if not session.is_u]


class FakeSession:
    def __init__(self, agent, mounts, output, script):
        self.agent = agent
        self.output = Path(output)
        self.mounts = {target: Path(source) for source, target, _ in mounts}
        self.script = script
        self.is_u = isinstance(agent, UAgent)
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
        if self.is_u:
            self.script.snapshots.append({
                str(path.relative_to(self.mounts['/solutions'])): path.read_text()
                for path in self.mounts['/solutions'].rglob('*') if path.is_file()
            })
            reply = self.script.advice.popleft()
        else:
            reply = self.script.solutions.popleft()
        if isinstance(reply, Exception):
            raise reply
        if not self.is_u:
            (self.mounts['/solution'] / 'main.py').write_text(reply)
            reply = 'Solution written.'
        return [{'type': 'agent_end', 'willRetry': False, 'messages': [{
            'role': 'assistant', 'stopReason': 'stop',
            'content': [{'type': 'text', 'text': reply}],
        }]}, {'type': 'agent_settled', 'aborted': False}]

    def close(self):
        self.closed = True
        (self.output / 'transcripts').mkdir(parents=True, exist_ok=True)
        (self.output / 'transcripts/session.jsonl').write_text('\n'.join(
            json.dumps({'prompt': text}) for text in self.messages))
        for name in ('stdout.txt', 'stderr.txt', 'proxy.log'):
            (self.output / name).write_text('')
        return RunResult(exit_code=0)


@pytest.fixture(autouse=True)
def botbox_script(monkeypatch):
    script = Script()

    class FakeBotbox:
        def __init__(self, agent, *, dockerfile):
            signature(Botbox).bind(agent, dockerfile=dockerfile)
            self.agent = agent

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def session(self, *, mounts, workdir, output):
            return FakeSession(self.agent, mounts, output, script)

    monkeypatch.setattr(importlib.import_module('surprisals_experiment.sdk.utils.botbox_session'),
                        'Botbox', FakeBotbox)
    return script


@pytest.fixture
def config(tmp_path):
    problem = tmp_path / 'problem'
    problem.mkdir()
    (problem / 'question.txt').write_text('Read an integer and print its double.')
    (problem / 'input_output.json').write_text(json.dumps({
        'inputs': ['3\n', '7\n'], 'outputs': ['6\n', '14\n'],
    }))
    return Config(u_mode='agent', api_key='test-key', problem_dir=problem, output=tmp_path / 'run',
                  u_model='u', t_model='t', t_samples=1, u_thinking='high', max_u_turns=1)


@pytest.fixture(autouse=True)
def chat_provider(monkeypatch, botbox_script):
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
            status = reply.get('status', 200)
            if status != 200:
                return httpx2.Response(status, json={'error': {'message': 'provider failed'}})
            deltas = reply['deltas']
            finish = reply.get('finish', 'stop')
        else:
            deltas = [{'role': 'assistant', 'reasoning': 'Thinking.'},
                      {'role': 'assistant', 'content': reply[:2]}, {'role': 'assistant', 'content': reply[2:]}]
            finish = 'stop'
        chunks = [
            {'id': 'test-chat', 'object': 'chat.completion.chunk', 'created': 1,
             'model': 'u', 'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}]}
            for delta in deltas
        ]
        if finish is not None:
            chunks.append({
                'id': 'test-chat', 'object': 'chat.completion.chunk', 'created': 1, 'model': 'u',
                'choices': [{'index': 0, 'delta': {}, 'finish_reason': finish}],
            })
        stream = ''.join(f'data: {json.dumps(chunk)}\n\n' for chunk in chunks)
        if isinstance(reply, dict) and reply.get('drop_stream'):
            class DroppedStream(httpx2.AsyncByteStream):
                async def __aiter__(self):
                    yield stream.encode()
                    raise httpx2.RemoteProtocolError('stream disconnected')
            return httpx2.Response(200, headers={'content-type': 'text/event-stream'},
                                   stream=DroppedStream())
        return httpx2.Response(200, headers={'content-type': 'text/event-stream'},
                              content=stream + 'data: [DONE]\n\n')

    def client(**kwargs):
        kwargs.setdefault('max_retries', 0)
        return AsyncOpenAI(**kwargs,
                           http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)))

    monkeypatch.setattr(importlib.import_module('surprisals_experiment.sdk.utils.u_session.open_u_session'),
                        'AsyncOpenAI', client)
    return requests
