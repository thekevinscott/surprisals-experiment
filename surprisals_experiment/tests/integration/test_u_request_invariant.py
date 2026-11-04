"""Exact HTTP message captures from main 91d8720, before file-based U history."""
import json
from pathlib import Path

import pytest

from surprisals_experiment.sdk import run_experiment
from surprisals_experiment.sdk.utils.u_chat.history import build_messages
from surprisals_experiment.sdk.utils.u_chat.compact import COMPACT

FIXTURES = Path(__file__).with_name('fixtures') / 'u_requests'

@pytest.mark.parametrize('mode', ['chat', 'flush', 'compaction', 'one_compaction'])
async def test_requests_match_main(config, botbox_script, chat_provider, mode):
    config.max_u_turns = 4
    config.u_flush = mode == 'flush'
    config.u_compact_chars = {'chat': 0, 'flush': 1, 'compaction': 1, 'one_compaction': 12000}[mode]
    advice = ['long first advice', 'double', 'longer advice', 'x']
    replies = []
    for index, text in enumerate(advice):
        if index and (mode == 'compaction' or (mode == 'one_compaction' and index == 1)):
            replies.append({'deltas': [{'role': 'assistant', 'content': 'Summary.',
                                       'reasoning': 'Summary reasoning.'}]})
        reasoning = 'r' * 15000 if mode == 'one_compaction' and index == 0 else 'Thinking.'
        replies.append({'deltas': [{'role': 'assistant', 'content': text, 'reasoning': reasoning,
            'reasoning_details': [{'type': 'reasoning.text', 'index': 0, 'text': reasoning,
                                  'format': 'provider.v1'}]}]})
    botbox_script.advice.extend(replies)
    botbox_script.solutions.extend(['print(int(input()) * 2)\n'] * 4)
    await run_experiment(config, on_delta=None)
    messages = [request['messages'] for request in chat_provider]
    assert messages == json.loads((FIXTURES / f'{mode}.json').read_text())
    assert not botbox_script.advice

    # Malformed diagnostics cannot affect file-derived inputs.
    transcript = config.u_transcripts / 'messages.jsonl'
    transcript.write_text('not a transcript\n{"torn":')
    advice_requests = [m for m in messages if m[-1]['content'] !=
                       COMPACT()]
    assert [build_messages(config, n) for n in range(4)] == advice_requests
    for n in range(4):
        saved = json.loads((config.advice_dir(n, 0) / 'reply.json').read_text())
        assert saved['content'] == advice[n]
        assert saved['reasoning_details'][0]['format'] == 'provider.v1'


async def test_existing_log_is_only_appended(config, botbox_script, chat_provider):
    transcript = config.u_transcripts / 'messages.jsonl'
    transcript.parent.mkdir(parents=True)
    original = b'not json\n{"torn":'
    transcript.write_bytes(original)
    botbox_script.advice.append('double')
    botbox_script.solutions.append('print(int(input()) * 2)\n')
    await run_experiment(config, on_delta=None)
    assert transcript.read_bytes().startswith(original)
    assert chat_provider[0]['messages'] == build_messages(config, 0)
