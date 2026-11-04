from pathlib import Path

ATTEMPTS = (Path(__file__).parent / 'attempts.sql').read_text()
RUN_FACTS = (Path(__file__).parent / 'run_facts.sql').read_text()
SAMPLE_FACTS = (Path(__file__).parent / 'sample_facts.sql').read_text()


def attempts_sql(samples):
    return ATTEMPTS.format(samples=samples)


def run_facts(config, before=None):
    attempts = attempts_sql(config.t_samples)
    if before is not None:
        attempts = f"SELECT * FROM ({attempts}) WHERE attempt < {before}"
    return RUN_FACTS.format(attempts=attempts)


def sample_facts(config, attempt):
    return SAMPLE_FACTS.format(samples=config.t_samples, tries=config.t_sample_retries + 1, attempt=attempt)
