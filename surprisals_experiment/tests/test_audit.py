"""Experiment boundaries: preflight, evaluation, and artifact ownership."""
import json
import tempfile
import unittest
from pathlib import Path
from typing import get_args
from unittest.mock import patch, AsyncMock

from botbox import RunResult
from pydantic import ValidationError

from surprisals_experiment.config import Config, ThinkingLevel
from surprisals_experiment.sdk import run_experiment, prompt_t
from surprisals_experiment.sdk.run_test_suite import run_test_suite

ATTEMPT = 'surprisals_experiment.sdk.run_experiment.produce_code.'
EXPERIMENT = 'surprisals_experiment.sdk.run_experiment.run_experiment.'


class AuditTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root/'question.txt').write_text('Print 7.')
        self.config = Config(api_key='dummy', problem_dir=self.root, output=self.root/'run',
                             u_model='u', u_thinking='high', t_model='t', t_samples=1, max_u_turns=1)

    async def test_invalid_suites_fail_before_starting_u(self):
        invalid = [None, {}, {'inputs': [], 'outputs': []},
                   {'inputs': ['x', 'y'], 'outputs': ['x']},
                   {'inputs': [[1]], 'outputs': ['1']},
                   {'inputs': [''], 'outputs': ['7'], 'fn_name': 'answer'}]
        with patch('surprisals_experiment.sdk.run_experiment.run_experiment.open_u_session') as start:
            for suite in invalid:
                with self.subTest(suite=suite):
                    self.config.test_suite_file.write_text(json.dumps(suite))
                    with self.assertRaises(ValueError):
                        await run_experiment(self.config, on_delta=None)
            self.config.test_suite_file.write_text('{')
            with self.assertRaises(ValueError):
                await run_experiment(self.config, on_delta=None)
            start.assert_not_called()

    async def test_evaluator_cannot_drop_unmatched_cases(self):
        (self.root/'main.py').write_text('print(7)')
        with self.assertRaises(ValueError):
            await run_test_suite({'inputs': ['', ''], 'outputs': ['7']}, self.root)

    async def attempt(self, exit_code):
        def t(config, advice, *, output, logs, on_delta=None):
            output.mkdir()
            (output/'main.py').write_text('print(7)')
            return RunResult(exit_code)
        self.config.test_suite_file.write_text(json.dumps({'inputs': [''], 'outputs': ['7']}))
        with patch(ATTEMPT+'prompt_t', side_effect=t), \
             patch(EXPERIMENT+'prepare_advice', return_value=('Print 7', 7)):
            return await run_experiment(self.config, on_delta=None)

    async def test_nonzero_t_exit_can_produce_valid_solution(self):
        output = await self.attempt(1)
        self.assertEqual(output, self.config.t_dir(0, 0)/'src')
        self.assertTrue(json.loads((self.config.t_dir(0, 0)/'tests.json').read_text())['all_passed'])

    async def test_daemon_failure_aborts_and_preserves_diagnostics(self):
        with self.assertRaisesRegex(RuntimeError, 'infrastructure'):
            await self.attempt(-1)
        self.assertIn('infrastructure', (self.config.attempt_dir(0)/'error.txt').read_text())
        self.assertEqual(json.loads((self.config.t_dir(0, 0)/'run.json').read_text())['exit_code'], -1)
        self.assertFalse((self.config.t_dir(0, 0)/'tests.json').exists())

    async def test_orchestration_errors_propagate_and_preserve_traceback(self):
        self.config.test_suite_file.write_text(json.dumps({'inputs': [''], 'outputs': ['7']}))
        with patch(ATTEMPT+'prompt_t', side_effect=OSError('disk failure')), \
             patch(EXPERIMENT+'prepare_advice', return_value=('Print 7', 7)):
            with self.assertRaisesRegex(OSError, 'disk failure'):
                await run_experiment(self.config, on_delta=None)
        self.assertIn('disk failure', (self.config.attempt_dir(0)/'error.txt').read_text())

    def test_sdk_thinking_values(self):
        values = self.config.model_dump()
        with self.assertRaises(ValidationError):
            Config(**(values | {'u_thinking': 'hgh'}))
        for level in get_args(ThinkingLevel):
            self.assertEqual(Config(**(values | {'u_thinking': level})).u_thinking, level)

    async def test_prompt_t_has_no_sibling_artifact_writes(self):
        result = RunResult(1)
        with patch('surprisals_experiment.sdk.utils.botbox_run.Botbox') as box:
            box.return_value.__aenter__.return_value.build = AsyncMock()
            box.return_value.__aenter__.return_value.run = AsyncMock(return_value=result)
            for name in ['first', 'second']:
                self.assertIs(await prompt_t(self.config, 'advice', output=self.root/name, logs=self.root/f'{name}-logs'), result)
                self.assertTrue((self.root/name).is_dir())
        self.assertFalse((self.root/'run.json').exists())
        self.assertFalse((self.root/'t_transcripts').exists())

    @patch('surprisals_experiment.sdk.run_test_suite.run_test_suite.TEST_TIMEOUT_SECONDS', .2)
    async def test_candidate_outcomes_and_evaluator_errors(self):
        cases = [('print(7)', True), ('print(8)', False), ('raise RuntimeError("bad code")', False),
                 ('import time; time.sleep(2)', False), ("import os; os.write(1,b'\\xff')", False),
                 ("import os; os.write(2,b'\\xff'); print(7)", False)]
        for source, passed in cases:
            with self.subTest(source=source):
                (self.root/'main.py').write_text(source)
                results = await run_test_suite({'inputs': [''], 'outputs': ['7']}, self.root)
                self.assertEqual(results.all_passed, passed)
        with self.assertRaises(FileNotFoundError):
            await run_test_suite({'inputs': [''], 'outputs': ['7']}, self.root/'absent')


if __name__ == '__main__':
    unittest.main()
