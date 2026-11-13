"""Where U transcripts live and their system prompt."""

import json

from u_flush_test import PASS, QUESTION, flush, outcome, played


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


async def test_every_transcript_has_one_system_prompt_at_the_top(config, execute_run_experiment):
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
    transcripts = sorted(config.output.glob('windows/*/forks/*/u/transcript.jsonl'))
    assert len(transcripts) == 4
    for path in transcripts:
        roles = [json.loads(line)['role'] for line in path.read_text().splitlines()]
        assert roles.count('user') == 6, path
        assert roles.count('system') == 1, (path, roles)
        assert roles[0] == 'system', (path, roles)
