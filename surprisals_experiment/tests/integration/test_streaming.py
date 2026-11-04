"""Prove T events tailed from stdout.txt reach redirected CLI stdout before the run ends."""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


RUNNER = r'''
import asyncio
import importlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import httpx2
from botbox import RunResult
from openai import AsyncOpenAI

root = Path(sys.argv[1])

class Box:
    def __init__(self, agent, **kwargs):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        pass
    async def build(self):
        return 'tag'
    async def run(self, command, *, mounts, workdir, output):
        import shlex
        args = shlex.split(command)
        assert args[args.index('--mode') + 1] == 'json'
        assert '--append-system-prompt' in args
        assert workdir == '/solution'
        source = next(Path(host) for host, target, _ in mounts if target == '/solution')
        (source / 'main.py').write_text('print(7)')
        output.mkdir(parents=True, exist_ok=True)
        with (output/'stdout.txt').open('w') as stdout:
            for kind, text in [('thinking_delta', 'THINKING_BEFORE_END'), ('text_delta', 'TEXT_BEFORE_END')]:
                stdout.write(json.dumps({'type':'message_update', 'assistantMessageEvent':{'type':kind, 'delta':text}}) + '\n')
                stdout.flush()
            while not (root/'release').exists():
                await asyncio.sleep(.01)
            stdout.write(json.dumps({'type':'agent_end', 'messages':[]}) + '\n')
        return RunResult(0)

def respond(request):
    chunk = {'id':'reply', 'object':'chat.completion.chunk', 'created':1, 'model':'u',
             'choices':[{'index':0, 'delta':{'role':'assistant', 'content':'Print 7.'}, 'finish_reason':'stop'}]}
    return httpx2.Response(200, headers={'content-type':'text/event-stream'},
                          content='data: ' + json.dumps(chunk) + '\n\ndata: [DONE]\n\n')

def client(**kwargs):
    return AsyncOpenAI(**kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)))

with patch('surprisals_experiment.sdk.utils.botbox_run.Botbox', Box), \
     patch('surprisals_experiment.sdk.utils.u_chat.open_u_chat.AsyncOpenAI', client):
    import runpy
    sys.argv = ['surprisals_experiment.cli.run', '--output', str(root/'run'),
                '--t-samples', '1', '--max-u-turns', '1', 'problem', str(root)]
    runpy.run_module('surprisals_experiment.cli.run', run_name='__main__')
'''


class StreamingTest(unittest.TestCase):
    def test_t_stdout_is_flushed_before_run_end(self):
        with tempfile.TemporaryDirectory(prefix='spar-stream-test-') as directory:
            root = Path(directory)
            (root / '.env').write_text('OPENROUTER_API_KEY=test-key\n')
            (root / 'question.txt').write_text('Print 7.')
            (root / 'input_output.json').write_text(json.dumps({'inputs': [''], 'outputs': ['7']}))
            env = dict(os.environ)
            env.pop('PYTHONUNBUFFERED', None)
            with (root/'stdout.log').open('w') as stdout, (root/'stderr.log').open('w') as stderr:
                process = subprocess.Popen([sys.executable, '-c', RUNNER, str(root)],
                                           stdout=stdout, stderr=stderr, env=env, cwd=root)
                try:
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline:
                        text = (root/'stdout.log').read_text()
                        if 'TEXT_BEFORE_END' in text or process.poll() is not None:
                            break
                        time.sleep(.01)
                    self.assertIsNone(process.poll(), (root/'stderr.log').read_text())
                    self.assertFalse((root/'release').exists())
                    self.assertIn('[T thinking]\nTHINKING_BEFORE_END', text)
                    self.assertIn('[T text]\nTEXT_BEFORE_END', text)
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
