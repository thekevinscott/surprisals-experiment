import json
import shutil

from ...run_test_suite.results import TestResult, TestSuiteResult
from ..prepare_feedback import describe_result
from ..prepare_flush import Attempt
from ..read_implementations import read_sources
from .artifacts import query
from .facts import attempts_sql, run_facts, sample_facts


def solutions(config, attempt):
    return [config.t_dir(attempt, sample) / 'src' for sample in range(config.t_samples)]


def results(config, attempt):
    return [TestSuiteResult([TestResult(**case) for case in json.loads(
        (config.t_dir(attempt, sample) / 'tests.json').read_text())['cases']])
        for sample in range(config.t_samples)]


async def action_inputs(config, session, action):
    facts = (await query(config, run_facts(config)))[0]
    attempt = facts['latest']
    for row in await query(config, f'SELECT * FROM ({attempts_sql(config.t_samples)}) WHERE measurement IS NOT NULL'):
        metadata = json.loads((config.advice_dir(row['attempt'], 0) / 'metadata.json').read_text())
        if 'tokens' in metadata:
            config.advice_measure.scores[row['advice']] = metadata['tokens']
    if action == 'write_advice':
        attempt = (attempt or 0) + bool(facts['complete'])
        session.attempt = attempt
        session.best_length = facts['best_length']
        session.best_advice = facts['best_advice']
        session.turns_without_improvement = facts['stale']
        prompt = (config.question_file.read_text() if attempt == 0 else
                  (config.attempt_dir(attempt - 1) / 'feedback.txt').read_text())
        return dict(u_session=session, prompt=prompt, attempt=attempt)
    if action == 'write_result':
        return dict(attempt=attempt, best_length=facts['best_length'],
                    best_solution=config.t_dir(facts['best'], 0) / 'src' if facts['best'] is not None else None)
    if action == 'run_tests':
        pending = []
        for sample, source in enumerate(solutions(config, attempt)):
            directory = config.t_dir(attempt, sample)
            if (directory / 'tests.json').exists():
                continue
            run = directory / 'run.json'
            if not run.exists() or json.loads(run.read_text())['exit_code'] < 0:
                shutil.rmtree(source, ignore_errors=True)
                source.mkdir()
            pending.append(source)
        return dict(solutions=pending, attempt=attempt)
    advice = (config.advice_dir(attempt, 0) / 'advice.txt').read_text()
    if action == 'score_advice':
        return dict(advice=advice, attempt=attempt)
    if action == 'write_solutions':
        pending = [row for row in await query(config, sample_facts(config, attempt)) if not row['has_solution']]
        return dict(advice=advice, attempt=attempt,
                    folders=[config.t_dir(attempt, row['sample']) for row in pending])
    previous = (await query(config, run_facts(config, before=attempt)))[0]
    history = []
    if config.u_flush:
        for row in await query(config, f'SELECT * FROM ({attempts_sql(config.t_samples)}) WHERE tested AND attempt < {attempt} ORDER BY attempt'):
            number = row['attempt']
            history.append(Attempt(
                number, row['advice'], row['measurement'],
                [describe_result(config, number, i, result) for i, result in enumerate(results(config, number))],
                bool(row['passed']), read_sources(solutions(config, number)),
                config.advice_measure.scores.get(row['advice']),
            ))
    measurement = json.loads((config.advice_dir(attempt, 0) / 'metadata.json').read_text())['measurement']
    return dict(u_session=session, attempt=attempt, advice=advice, measurement=measurement,
                solutions=solutions(config, attempt), results=results(config, attempt),
                best_length=previous['best_length'],
                best_solution=config.t_dir(previous['best'], 0) / 'src' if previous['best'] is not None else None,
                turns_without_improvement=previous['stale'], history=history)
