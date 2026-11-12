"""T has no tools and its single assistant reply is evaluated as Python."""

import json
import shlex
from pathlib import Path

import pytest
from botbox import RunResult

from surprisals_experiment.sdk.prompt_t import INSTRUCTIONS, prompt_t
from surprisals_experiment.sdk.run_test_suite.run_test_suite_for_t import run_test_suite_for_t

PROGRAM = 'print(int(input()) * 2)\n'


@pytest.mark.parametrize('check', ['no-tools', 'tested-reply'])
async def test_t_without_tools(config, monkeypatch, check):
    commands = []
    advice = 'Read an integer and print twice its value.'

    class ReplyBox:
        def __init__(self, agent, *, dockerfile):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def build(self):
            return 'fake'

        async def run(self, command, *, mounts, workdir, output):
            commands.append(shlex.split(command))
            mounted = {target: Path(source) for source, target, _ in mounts}
            assert (mounted['/advice'] / 'advice.md').read_text() == advice
            assert list(mounted['/solution'].iterdir()) == []
            # Only model output: no tool writes the solution on the host.
            event = {'type': 'agent_end', 'messages': [{
                'role': 'assistant', 'stopReason': 'stop', 'content': [
                    {'type': 'thinking', 'thinking': 'Use multiplication.'},
                    {'type': 'text', 'text': PROGRAM},
                ],
            }]}
            Path(output).mkdir(parents=True, exist_ok=True)
            (Path(output) / 'stdout.txt').write_text(json.dumps(event) + '\n')
            return RunResult(exit_code=0)

    monkeypatch.setattr('surprisals_experiment.sdk.utils.botbox_run.botbox_run.Botbox', ReplyBox)
    solution = config.output / 'src'
    result = await prompt_t(config, advice, output=solution, logs=config.output)
    assert result.exit_code == 0
    if check == 'no-tools':
        (args,) = commands
        assert '--no-tools' in args
        assert '--tools' not in args
        assert args[args.index('--system-prompt') + 1] == INSTRUCTIONS()
    else:
        assert (solution / 'main.py').read_text() == PROGRAM
        cases = json.loads((config.problem_dir / 'input_output.json').read_text())
        tested = await run_test_suite_for_t([
            {'input': stdin, 'output': stdout}
            for stdin, stdout in zip(cases['inputs'], cases['outputs'])
        ], solution)
        assert tested.all_passed
        assert tested.total == 2
