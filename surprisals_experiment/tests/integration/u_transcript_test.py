"""The provider receives the conversation persisted before each U call."""

import json
from unittest.mock import patch

import pytest
from u_flush_test import PASS, QUESTION, flush, outcome, played
from utils.mock_llm import MockLLM
from utils.world import U


@pytest.fixture
def recorded_windows(config):
    answer = MockLLM.answer
    seen = []

    async def recording(self, kind, sent):
        if kind is U:
            window = len(seen) // 2
            path = config.u_transcript if window == 0 else config.output / f'windows/{window}/forks/0/u/transcript.jsonl'
            entries = [json.loads(line) for line in path.read_text().splitlines()]
            # Main sends the latest system prompt and plain role/content from
            # completed turns; reasoning remains in the raw transcript.
            system = next(entry for entry in reversed(entries) if entry['role'] == 'system')
            messages = [system, *[entry for entry in entries if entry['role'] != 'system' and entry.get('_complete') is not False]]
            expected = [{key: entry[key] for key in ('role', 'content')} for entry in messages]
            assert sent['messages'] == expected
            if len(seen) % 2:
                reply = next(entry for entry in entries if entry.get('reasoning') == 'Think.')
                assert {'timestamp', 'completion_id', 'usage'} <= reply.keys()
                assert reply['completion_id'] == 'u'
                assert len(expected) == 4
            seen.append(window)
        return await answer(self, kind, sent)

    with patch.object(MockLLM, 'answer', recording):
        yield seen


async def test_transcript_matches_every_request(config, execute_run_experiment, recorded_windows):
    config.max_u_turns = 2
    windows = [
        [(QUESTION, 'double it', [PASS]), (None, 'double it', [PASS])],
        [(flush(0, 'double it', length=9), 'double', [PASS]), (None, 'double', [PASS])],
        [(flush(0, 'double', length=6), 'ok', [PASS]), (None, 'ok', [PASS])],
        [(flush(0, 'ok', length=2), 'ok', [PASS]), (None, 'ok', [PASS])],
    ]
    world, pending = played(windows, {'double it': {'score': 9}, 'double': {'score': 6}, 'ok': {'score': 2}}, config=config)
    world.append(outcome(config, 'windows/2/forks/0/turns/0', 8, pending))
    async with execute_run_experiment(config, world, u_layout=True):
        pass
    assert recorded_windows == [0, 0, 1, 1, 2, 2, 3, 3]


async def test_first_fork_owns_its_transcript(config, execute_run_experiment):
    config.max_u_turns = 1
    world, pending = played([
        [(QUESTION, 'ok', [PASS])],
        [(flush(0, 'ok', length=2), 'ok', [PASS])],
    ], {'ok': {'score': 2}}, config=config)
    world.append(outcome(config, 'windows/0/forks/0/turns/0', 2, pending))
    async with execute_run_experiment(config, world):
        pass
    assert (config.output / 'windows/0/forks/0/u/transcript.jsonl').is_file()
    assert not (config.output / 'u').exists()
