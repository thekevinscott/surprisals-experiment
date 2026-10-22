import io
from contextlib import redirect_stderr
import tempfile
import unittest
from pathlib import Path
from botbox import RunResult
from unittest.mock import patch

from surprisals_experiment.config import Config
from surprisals_experiment.sdk.utils.u_session import USession, USessionError, open_u_session
from surprisals_experiment.sdk.utils.u_agent import UAgent


class USessionTest(unittest.IsolatedAsyncioTestCase):
    async def test_failure_clears_event_callback(self):
        events = [
            {"type": "response", "success": False, "error": "provider failed"},
            {"type": "agent_end"},
        ]
        class ListSession:
            agent = UAgent("openrouter", "u", api_key="dummy", thinking="high")

            async def message(self, text):
                for event in events:
                    self.agent.turn_ended(event)
                return events
        u_session = USession(ListSession(), Path())
        with self.assertRaisesRegex(USessionError, "provider failed"):
            await u_session.prompt("question")
        self.assertIsNone(u_session.pi_session.agent.on_event)

    async def test_partial_eof_is_not_a_completed_reply(self):
        class PartialSession:
            agent = UAgent("openrouter", "u", api_key="dummy", thinking="high")

            async def message(self, text):
                events = [{'type':'message_end', 'message':{'role':'assistant','content':[{'type':'text','text':'partial'}]}}]
                for event in events:
                    self.agent.turn_ended(event)
                return events
        with self.assertRaisesRegex(USessionError, 'before completing'):
            await USession(PartialSession(), Path()).prompt('question')

    async def test_session_mounts_and_failure_diagnostics(self):
        opened = []
        class Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                self.result = self.close()

            def close(self):
                assert opened[-1][0][-1][0].exists(), "Remove snapshots only after Pi closes"
                return RunResult(exit_code=1, stdout='', stderr='failure', image='test-image', proxy='proxy-log',
                                              transcript={'.pi/agent/sessions/test.jsonl':'session-history\n'})
        class Box:
            def __init__(self, agent, *, dockerfile):
                self.agent = agent
                self.dockerfile = dockerfile
            async def __aenter__(self):
                return self
            async def __aexit__(self, *exc):
                pass
            def session(self, *, mounts, workdir):
                opened.append((mounts, workdir))
                return Session()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = Config(api_key='dummy', problem_dir=root/'problem', output=root/'run',
                            u_model='u', u_thinking='high', t_model='t', t_samples=1, max_u_turns=2, test_timeout_seconds=2,
                            u_advice_max_chars=100)
            stderr = io.StringIO()
            with redirect_stderr(stderr), patch('surprisals_experiment.sdk.utils.botbox_session.Botbox', Box):
                with self.assertRaisesRegex(RuntimeError, 'test failure'):
                    async with open_u_session(config) as u_session:
                        mounts, workdir = opened[0]
                        self.assertIn('fewer than 100 characters', mounts[0][0].read_text())
                        self.assertEqual(workdir, '/solutions')
                        self.assertEqual(u_session.solutions, mounts[-1][0])
                        self.assertFalse(u_session.solutions.is_relative_to(config.output))
                        (u_session.solutions/'snapshot.txt').write_text('source')
                        self.assertEqual([(target, mode) for _, target, mode in mounts], [('/u-config/u.txt','ro'),('/solutions','ro')])
                        self.assertFalse(any(source == config.problem_dir for source, _, _ in mounts))
                        raise RuntimeError('test failure')
            self.assertFalse((config.output/'u_run.json').exists())
            self.assertEqual(stderr.getvalue(), 'failure')
            self.assertEqual((config.output/'proxy_logs/u.log').read_text(), 'proxy-log')
            self.assertEqual((config.output/'u_transcripts/.pi/agent/sessions/test.jsonl').read_text(), 'session-history\n')
            self.assertFalse(opened[0][0][0][0].exists())
            self.assertFalse(opened[0][0][-1][0].exists())
            self.assertFalse((config.output/'u_solutions').exists())
            with patch('surprisals_experiment.sdk.utils.botbox_session.Botbox', Box):
                async with open_u_session(config) as u_session:
                    temporary_solutions = u_session.solutions
                    self.assertTrue(temporary_solutions.exists())
                self.assertFalse(temporary_solutions.exists())

    def test_launch_flags_and_model_quoting(self):
        import shlex
        model = "provider/model; echo should-not-execute"
        args = shlex.split(UAgent('openrouter', model=model, api_key='dummy', thinking='low').session_command())
        self.assertEqual(args[args.index('--model') + 1], model)
        self.assertEqual(args[0], 'u-pi')
        self.assertEqual(args[args.index('--thinking') + 1], 'low')
        self.assertEqual(args[args.index('--system-prompt') + 1], '/u-config/u.txt')



if __name__ == '__main__':
    unittest.main()
