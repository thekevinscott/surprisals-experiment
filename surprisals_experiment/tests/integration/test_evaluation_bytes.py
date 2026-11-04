"""Byte captures from main 64befe9 with deterministic clocks and fake providers."""

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from surprisals_experiment.sdk import run_experiment

FIXTURES = Path(__file__).with_name('fixtures') / 'evaluation_bytes'
PASS = 'import sys\nsys.stderr.write("note ☃\\r\\n")\nprint(int(input()) * 2)\n'
FAIL = 'print("wrong")\n'


@pytest.mark.parametrize('mode', ['chat', 'flush', 'compaction'])
async def test_artifacts_and_requests_match_main(config, botbox_script, chat_provider, monkeypatch, mode):
    # Only evaluator elapsed-time measurement is fixed; subprocess/asyncio clocks stay real.
    ticks = iter([10.0, 10.125] * 6)
    clock = SimpleNamespace(monotonic=lambda: next(ticks))
    for name in ['run_test_suite', 'run_test_suite_for_ts']:
        module = importlib.import_module(f'surprisals_experiment.sdk.run_test_suite.{name}')
        monkeypatch.setattr(module, 'time', clock, raising=False)
    config.u_flush = mode == 'flush'
    config.u_compact_chars = 1 if mode == 'compaction' else 0
    config.t_samples = 2
    config.max_u_turns = 3
    botbox_script.advice.extend(['long advice', 'summary one', 'bad', 'summary two', 'short']
                               if mode == 'compaction' else ['long advice', 'bad', 'short'])
    botbox_script.solutions.extend([PASS, PASS, PASS, FAIL, PASS, PASS])
    await run_experiment(config, on_delta=None)
    artifacts = {str(path.relative_to(config.output)): path.read_text()
                 for path in sorted(config.output.rglob('*'))
                 if path.name in {'feedback.txt', 'tests.json', 'result.json'}}
    expected = json.loads((FIXTURES / f'{mode}.json').read_text().replace('<RUN>', str(config.output)))
    assert chat_provider == expected['requests']
    for name, content in expected['artifacts'].items():
        assert (config.output / name).read_bytes() == content.encode()
    assert artifacts.keys() == expected['artifacts'].keys()
