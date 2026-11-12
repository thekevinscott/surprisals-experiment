"""The provider receives the conversation persisted before each U call."""

import json

from u_flush_test import PASS, QUESTION, flush, outcome, played
from utils.mock_llm import MockLLM
from utils.world import U


async def test_transcript_matches_every_request(config, execute_run_experiment, monkeypatch):
    config.max_u_turns = 2
    windows = [
        [(QUESTION, 'double it', [PASS]), (None, 'double it', [PASS])],
        [(flush(0, 'double it', length=9), 'double', [PASS]), (None, 'double', [PASS])],
        [(flush(0, 'double', length=6), 'ok', [PASS]), (None, 'ok', [PASS])],
        [(flush(0, 'ok', length=2), 'ok', [PASS]), (None, 'ok', [PASS])],
    ]
    world, pending = played(windows, {'double it': {'score': 9}, 'double': {'score': 6}, 'ok': {'score': 2}}, config=config)
    world.append(outcome(config, 'windows/2/forks/0/turns/0', 8, pending))
    answer = MockLLM.answer
    seen = []

    async def recording(self, kind, sent):
        if kind is U:
            window = len(seen) // 2
            directory = config.u_transcripts if window == 0 else config.output / f'windows/{window}/forks/0/u/transcripts'
            entries = [json.loads(line) for line in (directory / 'messages.jsonl').read_text().splitlines()]
            # Main sends the latest system prompt and plain role/content from
            # completed turns; reasoning remains in the raw transcript.
            system = next(entry for entry in reversed(entries) if entry['role'] == 'system')
            messages = [system, *[entry for entry in entries if entry['role'] != 'system' and entry.get('_complete') is not False]]
            expected = [{key: entry[key] for key in ('role', 'content')} for entry in messages]
            assert sent['messages'] == expected
            if len(seen) % 2:
                assert any(entry.get('reasoning') == 'Think.' for entry in entries)
                assert len(expected) == 4
            seen.append(window)
        return await answer(self, kind, sent)

    monkeypatch.setattr(MockLLM, 'answer', recording)
    async with execute_run_experiment(config, world, u_layout=True):
        pass
    assert seen == [0, 0, 1, 1, 2, 2, 3, 3]
