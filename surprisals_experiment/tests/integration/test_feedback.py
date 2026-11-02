import json
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

from botbox import RunResult

from surprisals_experiment.config import Config
from surprisals_experiment.sdk import run_experiment


class FakeU:
    def __init__(self, solutions):
        self.solutions = solutions
        self.commands = []

    async def prompt(self, text, *, on_delta=None):
        self.commands.append(text)
        on_delta('thinking', 'Thinking')
        return 'First advice' if len(self.commands) == 1 else 'Revised advice'


class FeedbackTest(unittest.IsolatedAsyncioTestCase):
    async def test_failed_candidates_get_clean_feedback_or_exhaust_normally(self):
        cases = [
            ('logs_and_mutation', "import sys\nfrom pathlib import Path\nPath('debug.txt').write_text(sys.stdin.read())\nPath('helpers.py').write_text('MUTATED')\nprint(0)", 2),
            ('binary_stdout', "import os\nos.write(1, b'\\xff')", 2),
            ('binary_stderr', "import os\nos.write(2, b'\\xff')\nprint(46874)", 2),
            ('exhaustion', 'print(0)', 1),
        ]
        for name, first_source, turns in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root/'question.txt').write_text('Read two integers and print their sum.')
                (root/'input_output.json').write_text(json.dumps({'inputs': ['19381 27493\n'], 'outputs': ['46874\n']}))
                config = Config(api_key='dummy', problem_dir=root, output=root/'run', u_model='u',
                                u_thinking='high', t_model='t', t_samples=1, max_u_turns=turns)
                pi, deltas, received, t_deltas = FakeU(root / 'shared'), [], [], []

                @asynccontextmanager
                async def start(config):
                    pi.solutions.mkdir()
                    yield pi

                def t(config, advice, *, output, logs, on_delta=None):
                    received.append(advice)
                    self.assertEqual(logs, output.parent)
                    on_delta("thinking", "T thinking")
                    output.mkdir()
                    source = first_source if len(received) == 1 else 'print(sum(map(int,input().split())))'
                    (output/'main.py').write_text(source)
                    (output/'helpers.py').write_text('VALUE = 42')
                    return RunResult(0)

                with patch('surprisals_experiment.sdk.run_experiment.run_experiment.open_u_session', side_effect=start), \
                     patch('surprisals_experiment.sdk.run_experiment.produce_code.prompt_t', side_effect=t):
                    result = await run_experiment(config, on_delta=lambda kind, text: deltas.append((kind, text)),
                                            on_t_delta=lambda kind, text: t_deltas.append((kind, text)))
                snapshot = root / "shared/0/0"
                self.assertEqual({p.name for p in snapshot.iterdir()}, {'main.py', 'helpers.py'})
                self.assertEqual((snapshot/'main.py').read_text(), first_source)
                self.assertEqual((snapshot/'helpers.py').read_text(), 'VALUE = 42')
                self.assertEqual(len(pi.commands), turns)
                self.assertEqual(t_deltas, [("thinking", "T thinking")] * turns)
                self.assertFalse((config.output/'u_solutions').exists())
                self.assertEqual(json.loads(config.result_file.read_text())['attempts'], turns)
                self.assertEqual(json.loads((config.t_dir(0, 0)/'run.json').read_text()), {'exit_code': 0})
                if turns == 1:
                    self.assertIsNone(result)
                    self.assertTrue((config.attempt_dir(0)/'feedback.txt').exists())
                    self.assertFalse(json.loads(config.result_file.read_text())['success'])
                else:
                    self.assertEqual(result, config.t_dir(1, 0)/'src')
                    self.assertEqual(received, ['First advice', 'Revised advice'])
                    feedback = pi.commands[1]
                    self.assertIn('VALUE = 42', feedback)
                    self.assertIn('passed 0 of 1 tests', feedback)
                    self.assertNotIn('19381', feedback)
                    self.assertEqual((config.attempt_dir(0)/'feedback.txt').read_text(), feedback)
                    self.assertIn(('thinking', 'Thinking'), deltas)


if __name__ == '__main__':
    unittest.main()
