import asyncio
import io
import json
import unittest
from collections import deque
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from botbox import Session
from surprisals_experiment.sdk.utils.u_agent import UAgent
from surprisals_experiment.sdk.utils.u_session import USession, USessionError


def end(error=None, reason='error', *, will_retry=False):
    message = {'role': 'assistant', 'stopReason': reason if error else 'stop',
               'content': [] if error else [{'type': 'text', 'text': 'advice'}]}
    if error:
        message['errorMessage'] = error
    return {'type': 'agent_end', 'messages': [message], 'willRetry': will_retry}


def settled(aborted=False):
    return {'type': 'agent_settled', 'aborted': aborted}


class RetryTest(unittest.IsolatedAsyncioTestCase):
    def session(self, events):
        self.lines = deque((json.dumps(e) + '\n').encode() for e in events)
        written = io.BytesIO()
        writer = Mock(drain=AsyncMock())
        writer.write.side_effect = written.write
        agent = UAgent('openrouter', 'test', api_key='dummy', thinking='high')
        client = asyncio.get_running_loop().create_future()
        async def readline():
            return self.lines.popleft() if self.lines else b''
        session = Session(agent, writer, client, readline)
        return USession(session, Path()), written

    async def test_recovery_sends_prompt_once_and_next_turn_stays_separate(self):
        events = []
        for i in range(1, 61):
            events += [end('terminated', will_retry=True), {'type': 'auto_retry_start', 'attempt': i,
                       'maxAttempts': 60, 'delayMs': min(5000 * 2**(i-1), 60000), 'errorMessage': 'terminated'}]
        events += [{'type': 'auto_retry_end', 'success': True, 'attempt': 60}, end(), settled(), end(), settled()]
        session, process = self.session(events)
        deltas = []
        self.assertEqual(await session.prompt('original', on_delta=lambda *x: deltas.append(x)), 'advice')
        self.assertEqual(len(process.getvalue().splitlines()), 1)
        self.assertEqual(len(deltas), 60)
        self.assertIn('60/60 in 60s', deltas[-1][1])
        self.assertEqual(await session.prompt('feedback'), 'advice')
        self.assertEqual(len(process.getvalue().splitlines()), 2)
        self.assertIsNone(session.pi_session.agent.on_event)

    async def test_exhaustion_and_cancellation_stop(self):
        for error in ('terminated', 'Retry cancelled'):
            with self.subTest(error=error):
                session, process = self.session([end('terminated'),
                    {'type': 'auto_retry_end', 'success': False, 'attempt': 60, 'finalError': error}, settled(aborted=error == 'Retry cancelled'), end(), settled()])
                with self.assertRaisesRegex(USessionError, error):
                    await session.prompt('original')
                self.assertEqual(len(process.getvalue().splitlines()), 1)
                self.assertIsNone(session.pi_session.agent.on_event)
                self.assertEqual(await session.prompt('next turn'), 'advice')

    async def test_permanent_error_and_abort_do_not_wait_for_retry(self):
        for error, reason in [('401 invalid API key', 'error'), ('cancelled', 'aborted'),
                              ('Provider returned error: maximum context length is 500 tokens', 'error')]:
            with self.subTest(error=error):
                session, process = self.session([end(error, reason), settled(aborted=reason == 'aborted'), end(), settled()])
                with self.assertRaisesRegex(USessionError, error):
                    await session.prompt('original')
                self.assertTrue(self.lines)
                self.assertEqual(await session.prompt('next turn'), 'advice')

    def test_retry_settings(self):
        from surprisals_experiment.retry_policy import pi_settings
        self.assertEqual(pi_settings()["maxRetries"], 60)
