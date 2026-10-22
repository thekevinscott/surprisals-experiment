import io
import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from botbox import Session
from surprisals_experiment.sdk.utils.u_agent import UAgent
from surprisals_experiment.sdk.utils.u_session import USession, USessionError


def end(error=None, reason='error'):
    message = {'role': 'assistant', 'stopReason': reason if error else 'stop',
               'content': [] if error else [{'type': 'text', 'text': 'advice'}]}
    if error:
        message['errorMessage'] = error
    return {'type': 'agent_end', 'messages': [message]}


class RetryTest(unittest.IsolatedAsyncioTestCase):
    def session(self, events):
        process = Mock(stdin=io.StringIO(), stdout=io.StringIO(
            ''.join(json.dumps(e) + '\n' for e in events)), stderr=io.StringIO())
        agent = UAgent('openrouter', 'test', api_key='dummy', thinking='high')
        session = Session(agent, process, 'container', 'image', lambda: ({}, ''))
        return USession(session, Path()), process

    async def test_recovery_sends_prompt_once_and_next_turn_stays_separate(self):
        events = []
        for i in range(1, 11):
            events += [end('terminated'), {'type': 'auto_retry_start', 'attempt': i,
                       'maxAttempts': 10, 'delayMs': 100 * 2**(i-1), 'errorMessage': 'terminated'}]
        events += [{'type': 'auto_retry_end', 'success': True, 'attempt': 10}, end(), end()]
        session, process = self.session(events)
        deltas = []
        self.assertEqual(await session.prompt('original', on_delta=lambda *x: deltas.append(x)), 'advice')
        self.assertEqual(len(process.stdin.getvalue().splitlines()), 1)
        self.assertEqual(len(deltas), 10)
        self.assertIn('10/10 in 51.2s', deltas[-1][1])
        self.assertEqual(await session.prompt('feedback'), 'advice')
        self.assertEqual(len(process.stdin.getvalue().splitlines()), 2)
        self.assertIsNone(session.pi_session.agent.on_event)
        self.assertIn('terminated', ''.join(session.pi_session._stdout))

    async def test_exhaustion_and_cancellation_stop(self):
        for error in ('terminated', 'Retry cancelled'):
            with self.subTest(error=error):
                session, process = self.session([end('terminated'),
                    {'type': 'auto_retry_end', 'success': False, 'attempt': 10, 'finalError': error}])
                with self.assertRaisesRegex(USessionError, error):
                    await session.prompt('original')
                self.assertEqual(len(process.stdin.getvalue().splitlines()), 1)
                self.assertIsNone(session.pi_session.agent.on_event)

    async def test_permanent_error_and_abort_do_not_wait_for_retry(self):
        for error, reason in [('401 invalid API key', 'error'), ('cancelled', 'aborted'),
                              ('Provider returned error: maximum context length is 500 tokens', 'error')]:
            with self.subTest(error=error):
                session, process = self.session([end(error, reason), end()])
                with self.assertRaisesRegex(USessionError, error):
                    await session.prompt('original')
                self.assertNotEqual(process.stdout.read(), '')

    def test_retry_settings(self):
        from importlib.resources import files
        settings = json.loads((files('surprisals_experiment') / 'docker/U/settings.json').read_text())['retry']
        self.assertTrue(settings['enabled'])
        self.assertEqual(settings['maxRetries'], 10)
        self.assertLessEqual(settings['baseDelayMs'] * 2**9, 60000)
