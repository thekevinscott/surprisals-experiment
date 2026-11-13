"""Each U conversation stores messages and reply usage in one transcript."""

import json

from u_flush_test import PASS, QUESTION, flush, outcome, played


async def test_run_keeps_one_transcript_per_u_conversation(config, execute_run_experiment):
    advice = 'Use a loop'
    windows = [[(QUESTION, advice, [PASS])], [(flush(0, advice, length=10), advice, [PASS])]]
    world, pending = played(windows, {advice: {'score': 10}}, config=config)
    world.append(outcome(config, 'windows/0/forks/0/turns/0', 2, pending))
    async with execute_run_experiment(config, world, u_layout=True):
        pass
    for folder in (config.output / 'windows/0/forks/0/u', config.output / 'windows/1/forks/0/u'):
        assert sorted(path.name for path in folder.iterdir()) == ['transcript.jsonl']
        messages = [json.loads(line) for line in (folder / 'transcript.jsonl').read_text().splitlines()]
        reply = messages[-2]
        assert messages[-1] == {'role': 'user', 'content': '<advice_length>10 characters</advice_length>'}
        metadata = json.loads((folder.parent / 'turns/0/metadata.json').read_text())
        assert reply == {'role': 'assistant', 'content': advice, 'reasoning': 'Think.',
                         'timestamp': '2026-01-01T00:00:00+00:00', 'completion_id': 'u', 'usage': None, 'u_messages': 2,
                         'u_request_sha256': metadata['u_request_sha256']}
