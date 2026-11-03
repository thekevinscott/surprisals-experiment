import json

from surprisals_experiment.sdk.run_experiment.state.artifacts import query
from surprisals_experiment.sdk.run_experiment.state.facts import run_facts, sample_facts


def save(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if isinstance(content, str) else json.dumps(content))


async def test_disk_facts_refresh_and_ignore_unrelated_artifacts(config):
    save(config.output / 'logs' / 'result.json', {'attempts': 99})
    save(config.output / 'attempts' / 'invalid' / 'feedback.txt', 'Ignore')
    save(config.advice_dir(4, 1) / 'advice.txt', 'Ignore secondary advice')
    save(config.t_dir(4, 0) / 'src' / 'tests.json', {'all_passed': True})
    assert await query(config, 'SELECT * FROM artifacts') == []
    empty = (await query(config, run_facts(config)))[0]
    assert empty == dict(latest=None, published=0, best=None, best_length=None,
                         best_advice=None, completed=0, stale=0, complete=0)
    advice = config.advice_dir(0, 0) / 'advice.txt'
    save(advice, 'First')
    assert (await query(config, run_facts(config)))[0]['latest'] == 0
    save(advice, 'Changed')
    assert (await query(config, 'SELECT content FROM artifacts')) == [{'content': 'Changed'}]
    advice.unlink()
    assert await query(config, 'SELECT * FROM artifacts') == []


async def test_sample_completion_uses_exit_status_retry_budget_and_saved_tests(config):
    config.t_samples = 5
    config.t_sample_retries = 1
    save(config.t_dir(2, 0) / 'run.json', {'exit_code': 0})
    save(config.t_dir(2, 0) / 'tests.json', {'all_passed': False})
    save(config.t_dir(2, 1) / 'run.json', {'exit_code': -1})
    save(config.t_dir(2, 1) / 'timeouts.txt', 'timeout\n')
    save(config.t_dir(2, 2) / 'timeouts.txt', 'timeout\ntimeout\n')
    save(config.t_dir(2, 3) / 'run.json', {'exit_code': 1})
    save(config.t_dir(1, 4) / 'run.json', {'exit_code': 0})
    assert await query(config, sample_facts(config, 2)) == [
        dict(sample=0, retries_left=2, has_solution=1, has_results=1),
        dict(sample=1, retries_left=1, has_solution=0, has_results=0),
        dict(sample=2, retries_left=0, has_solution=1, has_results=0),
        dict(sample=3, retries_left=2, has_solution=1, has_results=0),
        dict(sample=4, retries_left=2, has_solution=0, has_results=0),
    ]
    save(config.t_dir(2, 1) / 'timeouts.txt', 'timeout\ntimeout\n')
    assert (await query(config, sample_facts(config, 2)))[1]['has_solution'] == 1
    save(config.t_dir(2, 1) / 'timeouts.txt', 'timeout\n' * 3)
    assert (await query(config, sample_facts(config, 2)))[1]['retries_left'] == 0


async def test_best_stale_and_publication_require_complete_attempts(config):
    config.t_samples = 2
    for attempt, measurement, passes in [(0, 10, [True, True]), (1, 2, [True, False]),
                                          (2, 7, [True, True]), (3, 7, [True, True]),
                                          (4, 1, [True])]:
        save(config.advice_dir(attempt, 0) / 'advice.txt', f'Advice {attempt}')
        save(config.advice_dir(attempt, 0) / 'metadata.json', {'measurement': measurement})
        for sample, passed in enumerate(passes):
            save(config.t_dir(attempt, sample) / 'tests.json', {'all_passed': passed})
        save(config.attempt_dir(attempt) / 'feedback.txt', 'Feedback')
    save(config.result_file, {'attempts': 5})
    facts = (await query(config, run_facts(config)))[0]
    assert facts == dict(latest=4, published=5, best=2, best_length=7,
                         best_advice='Advice 2', completed=4, stale=1, complete=0)
    previous = (await query(config, run_facts(config, before=2)))[0]
    assert previous['latest'] == 1
    assert previous['best'] == 0
    assert previous['stale'] == 1
    save(config.t_dir(4, 1) / 'tests.json', {'all_passed': True})
    facts = (await query(config, run_facts(config)))[0]
    assert facts['best'] == 4
    assert facts['best_length'] == 1
    assert facts['stale'] == 0
    assert facts['completed'] == 5
    assert facts['complete'] == 1
    save(config.result_file, {'attempts': 4})
    assert (await query(config, run_facts(config)))[0]['complete'] == 0
