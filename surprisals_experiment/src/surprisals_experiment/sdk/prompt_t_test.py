"""Exercise the real T command and mount setup with Botbox replaced at its boundary."""

import shlex

import pytest
from surprisals_experiment.sdk.prompt_t import INSTRUCTIONS, prompt_t


@pytest.mark.parametrize(
    "advice",
    ["Use café.\r\nKeep 'quotes', $HOME and `literal` text.\n", "é" * 150_000],
    ids=["special-characters", "large"],
)
@pytest.mark.parametrize("fails", [False, True])
async def test_advice_file_preserves_bytes_and_never_enters_command(
    config, botbox_script, advice, fails
):
    botbox_script.solutions.append(
        RuntimeError("provider failed") if fails else "print(42)"
    )
    output = config.output / "src"
    if fails:
        with pytest.raises(RuntimeError, match="provider failed"):
            await prompt_t(config, advice, output=output, logs=config.output)
    else:
        result = await prompt_t(config, advice, output=output, logs=config.output)
        assert result.exit_code == 0
    (command,) = botbox_script.commands
    args = shlex.split(command)
    assert advice not in command
    assert len(command.encode()) < 128 * 1024
    assert args[args.index("-p") + 1] == "@/advice/advice.md"
    assert args[args.index("--system-prompt") + 1] == INSTRUCTIONS()
    assert args[args.index("--mode") + 1] == "json"
    (session,) = botbox_script.sessions
    assert session.messages == [advice]
    assert not session.mounts["/advice"].exists()


@pytest.mark.parametrize('reply', ['# café\n\nprint(42)\n', '```python\nprint(42)\n```', 'No solution.'])
async def test_reply_is_saved_verbatim_without_guessing_code_blocks(config, botbox_script, reply):
    botbox_script.solutions.append(reply)
    output = config.output / 'src'
    await prompt_t(config, 'Print 42.', output=output, logs=config.output)
    assert (output / 'main.py').read_bytes() == reply.encode('utf-8')
