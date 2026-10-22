"""Script Botbox sessions globally; keep orchestration and evaluation real."""

import importlib
import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from botbox import RunResult

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
    def __init__(self, agent, mounts, script):
        self.agent = agent
        self.mounts = {target: Path(source) for source, target, _ in mounts}
        self.script = script
        self.is_u = isinstance(agent, UAgent)
        self.messages = []
        self.closed = False
        script.sessions.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def message(self, text):
        self.messages.append(text)
        if self.is_u:
            self.script.snapshots.append({
                str(path.relative_to(self.mounts['/solutions'])): path.read_text()
                for path in self.mounts['/solutions'].rglob('main.py')
            })
            reply = self.script.advice.popleft()
        else:
            reply = self.script.solutions.popleft()
        if isinstance(reply, Exception):
            raise reply
        if not self.is_u:
            (self.mounts['/solution'] / 'main.py').write_text(reply)
            reply = 'Solution written.'
        return [{'type': 'agent_end', 'messages': [{
            'role': 'assistant', 'stopReason': 'stop',
            'content': [{'type': 'text', 'text': reply}],
        }]}]

    def close(self):
        self.closed = True
        return RunResult(stdout='', stderr='', exit_code=0,
                         transcript={'session.jsonl': '\n'.join(
                             json.dumps({'prompt': text}) for text in self.messages)},
                         proxy='', container='fake-container', image='fake-image')


@pytest.fixture(autouse=True)
def botbox_script(monkeypatch):
    script = Script()

    class FakeBotbox:
        def __init__(self, agent, **kwargs):
            self.agent = agent

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def session(self, *, mounts, workdir):
            return FakeSession(self.agent, mounts, script)

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
    return Config(api_key='test-key', problem_dir=problem, output=tmp_path / 'run',
                  u_model='u', t_model='t', t_samples=1, u_thinking='high', max_u_turns=5,
                  test_timeout_seconds=2)
