"""U's transcript on disk is exactly the conversation the provider received, through window 2."""

import json

from u_flush_test import PASS, QUESTION, flush, outcome, played
from utils.mock_llm import MockLLM
from utils.world import U


async def test_transcript_matches_every_request(config, execute_run_experiment, monkeypatch):
    config.max_u_turns = 2
    scores = {'double it': {'score': 9}, 'double': {'score': 6}, 'ok': {'score': 2}}
    windows = [
        [(QUESTION, 'double it', [PASS]), (None, 'double it', [PASS])],
        [(flush(0, 'double it', length=9), 'double', [PASS]), (None, 'double', [PASS])],
        [(flush(0, 'double', length=6), 'ok', [PASS]), (None, 'ok', [PASS])],
        [(flush(0, 'ok', length=2), 'ok', [PASS]), (None, 'ok', [PASS])],
    ]
    world, pending = played(windows, scores, config=config)
    world.append(outcome(config, 'windows/2/forks/0/turns/0', 8, pending))

    requests = []
    answer = MockLLM.answer

    async def recording(self, kind, sent):
        if kind is U:
            requests.append(sent['messages'])
        return await answer(self, kind, sent)

    monkeypatch.setattr(MockLLM, 'answer', recording)
    async with execute_run_experiment(config, world):
        pass

    for window, turns in enumerate(windows):
        sent = requests[:len(turns)]
        del requests[:len(turns)]
        transcripts = 'u/transcripts' if window == 0 else f'windows/{window}/forks/0/u/transcripts'
        lines = [json.loads(line) for line in (config.output / transcripts / 'messages.jsonl').read_text().splitlines()]
        for messages in sent:
            assert lines[:len(messages)] == messages
        assert lines[len(sent[-1]):] == [{'role': 'assistant', 'content': turns[-1][1]}]
    assert requests == []
