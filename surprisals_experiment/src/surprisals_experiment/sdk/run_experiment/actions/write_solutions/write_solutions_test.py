import asyncio
import json
from fake_botbox import FakeSession
from surprisals_experiment.sdk.run_experiment.actions.write_solutions import write_solutions
from surprisals_experiment.sdk.database import ExperimentDatabase, QuestionDatabase
from surprisals_experiment.sdk.turn import Turn
from surprisals_experiment.sdk.run import Run
from surprisals_experiment.sdk.run_experiment.run_experiment import actions
from advice_artifacts import write_advice


async def test_bounds_concurrency_and_retains_sample_order(config, botbox_script, monkeypatch):
    size = 2
    config.t_samples = 5
    config.t_pool_size = size
    started = [asyncio.Event() for _ in range(5)]
    release = [asyncio.Event() for _ in range(5)]
    finished = [asyncio.Event() for _ in range(5)]
    active = peak = 0
    completion = []
    original = FakeSession.message

    async def message(self, text):
        nonlocal active, peak
        sample = int(self.mounts['/solution'].parents[2].name)
        active += 1
        peak = max(peak, active)
        try:
            self.script.solutions.append('print(6)' if sample % 2 == 0 else 'print(0)')
            reply = await original(self, text)
            started[sample].set()
            await release[sample].wait()
            completion.append(sample)
            return reply
        finally:
            active -= 1
            finished[sample].set()

    monkeypatch.setattr(FakeSession, 'message', message)
    database = ExperimentDatabase(config.output)
    await actions["not_started"](Run(config, database, QuestionDatabase(config.problem_dir), actions))
    await database.dirsql.ready()
    turn = Turn(config, 0)
    turn.attempt_dir.mkdir(parents=True)
    write_advice(config, turn.attempt_dir, 'double it', 9)
    (config.problem_dir / 'input_output.json').write_text(json.dumps({'inputs': ['3\n'], 'outputs': ['6\n']}))
    task = asyncio.create_task(write_solutions(Run(config, database, QuestionDatabase(config.problem_dir), actions), turn))
    try:
        async with asyncio.timeout(5):
            capacity = min(size, 5)
            await asyncio.gather(*(event.wait() for event in started[:capacity]))
            assert not any(event.is_set() for event in started[capacity:])
            for sample in reversed(range(capacity)):
                release[sample].set()
                await finished[sample].wait()
            for event in release:
                event.set()
            await task
        assert peak == capacity
        assert completion[:capacity] == list(reversed(range(capacity)))
        assert [json.loads((config.t_dir(0, sample) / 'attempts/0/tests.json').read_text())['all_passed']
                for sample in range(5)] == [True, False, True, False, True]
        assert [session.messages for session in botbox_script.sessions] == [['double it']] * 5
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
