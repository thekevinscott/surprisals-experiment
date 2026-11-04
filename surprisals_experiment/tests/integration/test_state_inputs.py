import json
from types import SimpleNamespace

from surprisals_experiment.sdk.run_experiment.state.inputs import action_inputs


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) if isinstance(value, dict) else value)


def completed(config, attempt, advice, measurement, passed=True):
    write(config.advice_dir(attempt, 0) / 'advice.txt', advice)
    write(config.advice_dir(attempt, 0) / 'metadata.json', {'measurement': measurement, 'tokens': [[advice, measurement]]})
    write(config.t_dir(attempt, 0) / 'run.json', {'exit_code': 0})
    write(config.t_dir(attempt, 0) / 'src' / 'nested' / 'main.py', 'original')
    write(config.t_dir(attempt, 0) / 'tests.json', {'all_passed': passed, 'cases': [dict(index=0, passed=passed, status='passed' if passed else 'failed', stdout='', stderr='', exit_code=0)]})


async def test_advice_recovers_previous_feedback_and_best(config):
    config.output.mkdir()
    session = SimpleNamespace()
    first = await action_inputs(config, session, 'write_advice')
    assert first['attempt'] == 0
    assert first['prompt'] == config.question_file.read_text()
    completed(config, 0, 'Double.', 7)
    write(config.attempt_dir(0) / 'feedback.txt', 'Try shorter.')
    write(config.result_file, {'attempts': 1})
    recovered = await action_inputs(config, session, 'write_advice')
    assert recovered == dict(u_session=session, prompt='Try shorter.', attempt=1)
    assert (session.attempt, session.best_length, session.best_advice, session.turns_without_improvement) == (1, 7, 'Double.', 0)
    assert config.advice_measure.scores['Double.'] == [['Double.', 7]]


async def test_scoring_and_generation_read_saved_advice(config):
    write(config.advice_dir(0, 0) / 'advice.txt', 'Saved.')
    session = SimpleNamespace()
    assert await action_inputs(config, session, 'score_advice') == dict(advice='Saved.', attempt=0)
    assert await action_inputs(config, session, 'write_solutions') == dict(advice='Saved.', attempt=0, folders=[config.t_dir(0, 0)])


async def test_tests_skip_finished_samples_and_clear_timed_out_sources(config):
    config.t_samples = 3
    write(config.advice_dir(0, 0) / 'advice.txt', 'Saved.')
    write(config.t_dir(0, 0) / 'tests.json', {'all_passed': True})
    write(config.t_dir(0, 1) / 'run.json', {'exit_code': 0})
    write(config.t_dir(0, 1) / 'src' / 'main.py', 'finished')
    write(config.t_dir(0, 2) / 'run.json', {'exit_code': -1})
    write(config.t_dir(0, 2) / 'src' / 'main.py', 'partial')
    inputs = await action_inputs(config, None, 'run_tests')
    assert inputs == dict(attempt=0, solutions=[config.t_dir(0, i) / 'src' for i in (1, 2)])
    assert (inputs['solutions'][0] / 'main.py').read_text() == 'finished'
    assert list(inputs['solutions'][1].iterdir()) == []


async def test_feedback_uses_prior_counters_and_solution_sources(config):
    config.u_flush = True
    completed(config, 0, 'First.', 6)
    write(config.attempt_dir(0) / 'feedback.txt', 'Try again.')
    completed(config, 1, 'Second.', 7, False)
    session = SimpleNamespace()
    inputs = await action_inputs(config, session, 'write_feedback')
    assert (inputs['attempt'], inputs['measurement'], inputs['best_length'], inputs['turns_without_improvement']) == (1, 7, 6, 0)
    assert inputs['best_solution'] == config.t_dir(0, 0) / 'src'
    assert not inputs['results'][0].all_passed
    assert len(inputs['history']) == 1
    assert inputs['history'][0].sources == {'0': {'nested/main.py': 'original'}}
    assert inputs['solutions'] == [config.t_dir(1, 0) / 'src']
    result = await action_inputs(config, session, 'write_result')
    assert result == dict(attempt=1, best_length=6, best_solution=config.t_dir(0, 0) / 'src')


async def test_generation_inputs_select_incomplete_folders(config):
    config.t_samples = 4
    config.t_sample_retries = 2
    write(config.advice_dir(0, 0) / 'advice.txt', 'Saved.')
    write(config.t_dir(0, 0) / 'run.json', {'exit_code': 0})
    write(config.t_dir(0, 1) / 'run.json', {'exit_code': -1})
    write(config.t_dir(0, 1) / 'timeouts.txt', 'timeout\n')
    write(config.t_dir(0, 2) / 'timeouts.txt', 'timeout\n' * 3)
    session = SimpleNamespace()
    inputs = await action_inputs(config, session, 'write_solutions')
    assert inputs == dict(advice='Saved.', attempt=0,
                          folders=[config.t_dir(0, 1), config.t_dir(0, 3)])
