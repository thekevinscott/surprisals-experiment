"""Single U transcripts retain messages and usage when exported."""

import json
import tempfile
import unittest
from pathlib import Path

from docent_upload import convert


class SingleTranscriptTest(unittest.TestCase):
    def test_exports_root_and_fork_conversations_with_failed_reply_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / 'experiment' / 'run'
            run.mkdir(parents=True)
            (run / 'settings.json').write_text('{}')
            (run / 'run.json').write_text(json.dumps({'params': {'problem-dir': '/data/problem'}, 'exit_code': 0}))
            failed = {'role': 'assistant', 'reasoning': 'Thinking.', 'reasoning_details': [{'text': 'detail'}],
                      '_complete': False, 'completion_id': 'failed', 'usage': {'completion_tokens': 3},
                      'provider_error': {'message': 'failed'}, 'timestamp': '2026-01-01T00:00:00+00:00'}
            messages = [{'role': 'system', 'content': 'system'}, {'role': 'user', 'content': 'question'},
                        failed, {'role': 'assistant', 'content': 'advice', '_complete': True, 'usage': None}]
            for path in [run / 'u/transcript.jsonl', run / 'windows/1/forks/0/u/transcript.jsonl']:
                path.parent.mkdir(parents=True)
                path.write_text(''.join(json.dumps(message) + '\n' for message in messages))
            _, runs, missing = convert(run)
            self.assertEqual(missing, [])
            self.assertEqual(len(runs), 2)
            for exported in runs:
                saved = exported.transcripts[0].messages
                self.assertEqual([message.role for message in saved], ['system', 'user', 'assistant', 'assistant'])
                self.assertEqual(saved[0].content, 'system')
                self.assertEqual(saved[2].metadata, {key: value for key, value in failed.items() if key != 'role'})
                self.assertEqual(saved[2].content[0].reasoning, 'Thinking.')
                self.assertEqual(saved[3].content, 'advice')
