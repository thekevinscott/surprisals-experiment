from dirsql import DirSQL

from .artifacts import surprisal_tables
from .facts import attempts_sql, run_facts, sample_facts


async def read_state(config):
    db = DirSQL(str(config.output), tables=surprisal_tables(config.output))
    run = (await db.query(run_facts(config)))[0]
    if run['latest'] is None:
        return 'not_started'
    if run['complete']:
        if (run['stale'] >= config.max_turns_without_improvement
                or (config.max_u_turns is not None and run['completed'] >= config.max_u_turns)):
            return 'exhausted'
        return 'next_attempt'
    attempt = (await db.query(
        f"SELECT * FROM ({attempts_sql(config.t_samples)}) WHERE attempt = {run['latest']}"
    ))[0]
    if attempt['advice'] is None:
        return 'advice_missing'
    if attempt['measurement'] is None:
        return 'unscored'
    if attempt['tested']:
        return 'result_missing' if attempt['feedback'] else 'feedback_missing'
    samples = await db.query(sample_facts(config, run['latest']))
    if any(not sample['has_solution'] for sample in samples):
        return 'solutions_missing'
    if any(not sample['has_results'] for sample in samples):
        return 'untested'
    return 'feedback_missing'
