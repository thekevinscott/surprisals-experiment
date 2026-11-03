"""T generation follows the supplied sample selection and attempt budgets."""
import asyncio
import json

from conftest import FakeSession
from surprisals_experiment.sdk.run_experiment.actions.write_solutions import write_solutions

SOURCE = 'print(int(input()) * 2)\n'


async def test_generates_exactly_selected_samples_in_supplied_order(config, botbox_script):
    config.t_samples = 4
    config.t_pool_size = 1
    botbox_script.solutions.extend([SOURCE, 'print(0)\n'])
    snapshot = config.output / 'snapshot'
    outputs = await write_solutions(
        config, attempt=0, advice='Double.', snapshot=snapshot,
        samples=[3, 1], retry_budgets={3: 1, 1: 1},
    )
    assert outputs == [config.t_dir(0, sample) / 'src' for sample in [3, 1]]
    assert len(botbox_script.sessions) == 2
    assert all(session.closed for session in botbox_script.sessions)
    assert not config.t_dir(0, 0).exists()
    assert not config.t_dir(0, 2).exists()
    for sample, source in [(3, SOURCE), (1, 'print(0)\n')]:
        assert (snapshot / str(sample) / 'main.py').read_text() == source
        assert (config.t_dir(0, sample) / 'src/main.py').read_text() == source
        assert json.loads((config.t_dir(0, sample) / 'run.json').read_text()) == {'exit_code': 0}


async def test_supplied_budgets_bound_each_samples_attempts(config, botbox_script, monkeypatch):
    config.t_sample_retries = 5
    config.t_sample_timeout = .01

    async def message(self, text):
        (self.mounts['/solution'] / 'partial.py').write_text('partial')
        await asyncio.Event().wait()

    monkeypatch.setattr(FakeSession, 'message', message)
    snapshot = config.output / 'snapshot'
    outputs = await write_solutions(
        config, attempt=0, advice='Double.', snapshot=snapshot,
        samples=[2, 0, 1], retry_budgets={2: 0, 0: 1, 1: 2},
    )
    assert outputs == [config.t_dir(0, sample) / 'src' for sample in [2, 0, 1]]
    assert len(botbox_script.sessions) == 3
    assert all(session.closed for session in botbox_script.sessions)
    assert not (config.t_dir(0, 2) / 'timeouts.txt').exists()
    for sample, budget in [(0, 1), (1, 2)]:
        assert len((config.t_dir(0, sample) / 'timeouts.txt').read_text().splitlines()) == budget
    for sample, output in zip([2, 0, 1], outputs):
        assert list(output.iterdir()) == []
        assert list((snapshot / str(sample)).iterdir()) == []


async def test_empty_selection_runs_no_samples(config, botbox_script):
    snapshot = config.output / 'snapshot'
    assert await write_solutions(
        config, attempt=0, advice='Double.', snapshot=snapshot,
        samples=[], retry_budgets={},
    ) == []
    assert botbox_script.sessions == []
    assert (snapshot / 'advice.txt').read_text() == 'Double.'
