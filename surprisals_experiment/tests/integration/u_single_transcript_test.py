"""U keeps its conversation and reply usage in one transcript per fork."""

import json

from u_flush_test import PASS, QUESTION, flush, outcome, played


async def test_only_one_transcript_with_usage_on_replies(config, execute_run_experiment):
    world, pending = played([
        [(QUESTION, 'double', [PASS])],
        [(flush(0, 'double', length=6), 'double', [PASS])],
    ], {'double': {'score': 6}}, config=config)
    world.append(outcome(config, 'windows/0/forks/0/turns/0', 2, pending))
    async with execute_run_experiment(config, world):
        pass
    for directory in [config.output / 'u', config.output / 'windows/1/forks/0/u']:
        assert sorted(path.name for path in directory.iterdir()) == ['transcript.jsonl']
        entries = [json.loads(line) for line in (directory / 'transcript.jsonl').read_text().splitlines()]
        replies = [entry for entry in entries if entry['role'] == 'assistant']
        assert len(replies) == 1
        assert replies[0]['usage'] is None
        assert replies[0]['completion_id'] == 'u'
        assert replies[0]['timestamp'] == '2026-01-01T00:00:00+00:00'
