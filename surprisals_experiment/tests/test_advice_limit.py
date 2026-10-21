import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from surprisals_experiment.config import Config
from surprisals_experiment.sdk import run_experiment


class AdviceLimitTest(unittest.TestCase):
    def test_rewrites_are_separate_from_test_feedback(self):
        for limit, replies, retries, exhausted in [
            (5, ['12345', '123456', '1234', 'abcde', 'abc'], 2, False),
            (5, ['12345', '123456', '12345'], 2, True),
            (None, ['unlimited advice', 'more unlimited advice'], 0, False),
        ]:
            with self.subTest(limit=limit, exhausted=exhausted), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root/'question.txt').write_text('Question')
                (root/'input_output.json').write_text(json.dumps({'inputs': ['1'], 'outputs': ['2']}))
                output = root/'run'
                output.mkdir()
                config = Config(api_key='dummy', problem_dir=root, output=output, u_model='u',
                                t_model='t', t_samples=1, u_thinking='high', max_u_turns=2, test_timeout_seconds=1,
                                u_advice_max_chars=limit, u_advice_retries=retries)
                session = SimpleNamespace(prompt=Mock(side_effect=replies), solutions=root/'solutions')

                @contextmanager
                def open_session(config):
                    yield session

                attempt = Mock(side_effect=[(root/'first', [SimpleNamespace(all_passed=False)]),
                                            (root/'second', [SimpleNamespace(all_passed=True)])])
                module = 'surprisals_experiment.sdk.run_experiment.run_experiment'
                with patch(module+'.open_u_session', open_session), \
                     patch(module+'.run_attempt', attempt), \
                     patch(module+'.prepare_feedback', return_value='Test feedback'):
                    if exhausted:
                        with self.assertRaisesRegex(RuntimeError, 'after 2 retries'):
                            run_experiment(config, on_delta=None)
                        attempt.assert_not_called()
                        self.assertEqual(session.prompt.call_count, 3)
                    else:
                        self.assertEqual(run_experiment(config, on_delta=None), root/'second')
                        self.assertEqual(attempt.call_count, 2)
                        self.assertEqual(json.loads(config.result_file.read_text())['attempts'], 2)
                        prompts = [c.args[0] for c in session.prompt.call_args_list]
                        self.assertIn('Test feedback', prompts)
                        if limit:
                            self.assertIn('Your advice was 5 characters', prompts[1])
                            self.assertIn('fewer than 5 characters', prompts[1])
                            self.assertEqual([c.kwargs['advice'] for c in attempt.call_args_list],
                                             ['1234', 'abc'])

                saved = sorted(output.glob('attempts/*/advices/*/advice.txt'))
                self.assertEqual([p.read_text() for p in saved], replies)
                for path, advice in zip(saved, replies):
                    metadata = json.loads(path.with_name('metadata.json').read_text())
                    self.assertEqual(metadata, {
                        'rejected': limit is not None and len(advice) >= limit,
                        'measurement': len(advice),
                    })
                self.assertFalse(list(output.glob('attempts/*/u.txt')))
