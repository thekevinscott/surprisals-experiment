"""Prove T events tailed from stdout.txt reach redirected CLI stdout before the run ends."""

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

from botbox import RunResult
from surprisals_experiment.sdk import prompt_t

root = Path(sys.argv[1])

async def experiment(config, *, on_delta, on_t_delta):
    class Box:
        def __init__(self, agent, **kwargs):
            self.agent = agent
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
            assert output == root/'logs'
            output.mkdir(parents=True, exist_ok=True)
            with (output/'stdout.txt').open('w') as stdout:
                for kind, text in [('thinking_delta', 'THINKING_BEFORE_END'), ('text_delta', 'TEXT_BEFORE_END')]:
                    stdout.write(json.dumps({'type':'message_update', 'assistantMessageEvent':{'type':kind, 'delta':text}}) + '\n')
                    stdout.flush()
                while not (root/'release').exists():
                    await asyncio.sleep(.01)
                stdout.write(json.dumps({'type':'agent_end', 'messages':[]}) + '\n')
            return RunResult(0)
    with patch('surprisals_experiment.sdk.utils.botbox_run.Botbox', Box):
        result = await prompt_t(config, 'question', output=root/'solution', logs=root/'logs', on_delta=on_t_delta)
    assert result.exit_code == 0

cli = importlib.import_module('surprisals_experiment.cli.main')
with patch.object(cli, 'find_dotenv', return_value='unused'), \
     patch.object(cli, 'dotenv_values', return_value={'OPENROUTER_API_KEY':'dummy'}), \
     patch.object(cli, 'run_experiment', side_effect=experiment):
    import runpy
    sys.argv = ['surprisals_experiment.cli.run', '--output', str(root/'run'), 'problem', str(root)]
    runpy.run_module('surprisals_experiment.cli.run', run_name='__main__')
'''


class StreamingTest(unittest.TestCase):
    def test_t_stdout_is_flushed_before_run_end(self):
        with tempfile.TemporaryDirectory(prefix='spar-stream-test-') as directory:
            root = Path(directory)
            env = dict(os.environ)
            env.pop('PYTHONUNBUFFERED', None)
            with (root/'stdout.log').open('w') as stdout, (root/'stderr.log').open('w') as stderr:
                process = subprocess.Popen([sys.executable, '-c', RUNNER, str(root)],
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
