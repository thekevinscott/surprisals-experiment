import pytest

from state_machine import Stop, state_machine


async def test_file_backed_machine_restarts_without_repeating_work(tmp_path):
    advice = tmp_path / "advice.txt"
    score = tmp_path / "score.txt"
    calls = []

    async def read_state():
        if not advice.exists():
            return "advice_missing"
        return "done" if score.exists() else "unscored"

    async def write_advice():
        calls.append("advice")
        advice.write_text("Double the input.")
        raise InterruptedError("stopped after publishing advice")

    async def score_advice():
        calls.append("score")
        score.write_text(str(len(advice.read_text())))

    actions = {"advice_missing": write_advice, "unscored": score_advice, "done": Stop}
    with pytest.raises(InterruptedError, match="stopped after publishing advice"):
        await state_machine(state=read_state, actions=actions)
    assert advice.read_text() == "Double the input."
    assert not score.exists()

    await state_machine(state=read_state, actions=actions)
    assert score.read_text() == str(len("Double the input."))
    assert calls == ["advice", "score"]
    assert await read_state() == "done"


async def test_unknown_state_raises():
    async def read_state():
        return "unknown"

    with pytest.raises(KeyError, match="unknown"):
        await state_machine(state=read_state, actions={"done": Stop})


async def test_forwards_argument_to_state_and_action():
    calls = []

    async def read_state(events):
        events.append("state")
        return "done" if "action" in events else "work"

    async def action(events):
        events.append("action")

    await state_machine(read_state, {"work": action, "done": Stop}, calls)

    assert calls == ["state", "action", "state"]
