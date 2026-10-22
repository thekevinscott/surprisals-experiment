"""Prove the real botbox reader reaches redirected CLI stdout before turn end."""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


RUNNER = r'''
import importlib
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from botbox import Session
from surprisals_experiment.sdk.utils.u_agent import UAgent
from surprisals_experiment.sdk.utils.u_session import USession
from surprisals_experiment.sdk import prompt_t

root = Path(sys.argv[1])
child = r"""
import json, sys, time
from pathlib import Path
sys.stdin.readline()
for kind, text in [('thinking_delta', 'THINKING_BEFORE_END'), ('text_delta', 'TEXT_BEFORE_END')]:
    print(json.dumps({'type':'message_update', 'assistantMessageEvent':{'type':kind, 'delta':text}}), flush=True)
while not Path(sys.argv[1]).exists():
    time.sleep(.01)
print(json.dumps({'type':'agent_end', 'messages':[{'role':'assistant', 'stopReason':'stop', 'content':[{'type':'text','text':'TEXT_BEFORE_END'}]}]}), flush=True)
sys.stdin.read()
"""

async def experiment(config, *, on_delta, on_t_delta):
    if sys.argv[2] == 'T':
        class Box:
            def __init__(self, agent, **kwargs):
                self.agent = agent
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def session(self, *, mounts, workdir):
                import shlex
                args = shlex.split(self.agent.session_command())
                assert args[args.index('--mode') + 1] == 'rpc'
                assert '--append-system-prompt' in args
                assert workdir == '/solution'
                process = subprocess.Popen([sys.executable, '-c', child, str(root/'release')],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                return Session(self.agent, process, 'test-container', 'test-image',
                               lambda: ({'session.jsonl': 'saved transcript'}, 'proxy log'))
        with patch('surprisals_experiment.sdk.utils.botbox_session.Botbox', Box):
            result = await prompt_t(config, 'question', output=root/'solution', on_delta=on_t_delta)
        assert result.exit_code == 0
        assert result.transcript == {'session.jsonl': 'saved transcript'}
        assert result.proxy == 'proxy log'
        return
    process = subprocess.Popen([sys.executable, '-c', child, str(root/'release')],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    agent = UAgent('openrouter', 'unused', api_key='dummy', thinking='high')
    with Session(agent, process, 'test-container', 'test-image', lambda: ({}, '')) as pi_session:
        advice = await USession(pi_session, root).prompt('question', on_delta=on_delta)
        assert advice == 'TEXT_BEFORE_END'
        assert agent.on_event is None
    assert pi_session.result.exit_code == 0

cli = importlib.import_module('surprisals_experiment.cli.main')
with patch.object(cli, 'find_dotenv', return_value='unused'), \
     patch.object(cli, 'dotenv_values', return_value={'OPENROUTER_API_KEY':'dummy'}), \
     patch.object(cli, 'run_experiment', side_effect=experiment):
    cli.main(['--output', str(root/'run'), 'problem', str(root)])
'''


class StreamingTest(unittest.TestCase):
    def test_u_stdout_is_flushed_before_agent_end(self):
        self.check_stream('U')

    def test_t_stdout_is_flushed_before_agent_end(self):
        self.check_stream('T')

    def check_stream(self, actor):
        with tempfile.TemporaryDirectory(prefix='spar-stream-test-') as directory:
            root = Path(directory)
            env = dict(os.environ)
            env.pop('PYTHONUNBUFFERED', None)
            with (root/'stdout.log').open('w') as stdout, (root/'stderr.log').open('w') as stderr:
                process = subprocess.Popen([sys.executable, '-c', RUNNER, str(root), actor],
                                           stdout=stdout, stderr=stderr, env=env)
                try:
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline:
                        text = (root/'stdout.log').read_text()
                        if 'TEXT_BEFORE_END' in text or process.poll() is not None:
                            break
                        time.sleep(.01)
                    self.assertIsNone(process.poll(), (root/'stderr.log').read_text())
                    self.assertFalse((root/'release').exists())
                    self.assertIn(f'[{actor} thinking]\nTHINKING_BEFORE_END', text)
                    self.assertIn(f'[{actor} text]\nTEXT_BEFORE_END', text)
                finally:
                    (root/'release').touch()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                        raise
                self.assertEqual(process.returncode, 0, (root/'stderr.log').read_text())
            text = (root/'stdout.log').read_text()
            self.assertEqual(text.count('THINKING_BEFORE_END'), 1)
            self.assertEqual(text.count('TEXT_BEFORE_END'), 1)
            self.assertFalse((root/'run/u.jsonl').exists())



if __name__ == '__main__':
    unittest.main()
