def attempts_sql(samples):
    return f"""
        SELECT attempt,
          max(CASE WHEN kind = 'advice.txt' THEN content END) AS advice,
          max(CASE WHEN kind = 'metadata.json' THEN json_extract(content, '$.measurement') END) AS measurement,
          max(kind = 'feedback.txt') AS feedback,
          sum(kind = 'tests.json') = {samples} AS tested,
          sum(CASE WHEN kind = 'tests.json' THEN json_extract(content, '$.all_passed') ELSE 0 END) = {samples} AS passed
        FROM artifacts WHERE attempt IS NOT NULL GROUP BY attempt
    """


def run_facts(config, before=None):
    attempts = attempts_sql(config.t_samples)
    if before is not None:
        attempts = f"SELECT * FROM ({attempts}) WHERE attempt < {before}"
    return f"""
        WITH attempts AS ({attempts}), best AS (
            SELECT attempt, measurement, advice FROM attempts WHERE tested AND passed
            ORDER BY measurement, attempt LIMIT 1
        ) SELECT
            (SELECT max(attempt) FROM attempts) AS latest,
            coalesce((SELECT json_extract(content, '$.attempts') FROM artifacts WHERE kind = 'result'), 0) AS published,
            (SELECT attempt FROM best) AS best,
            (SELECT measurement FROM best) AS best_length,
            (SELECT advice FROM best) AS best_advice,
            (SELECT count(*) FROM attempts WHERE feedback AND tested) AS completed,
            (SELECT count(*) FROM attempts WHERE tested AND attempt > coalesce((SELECT attempt FROM best), -1)) AS stale,
            coalesce((SELECT feedback AND tested FROM attempts ORDER BY attempt DESC LIMIT 1), 0)
              AND coalesce((SELECT json_extract(content, '$.attempts') FROM artifacts WHERE kind = 'result'), 0)
                  > (SELECT max(attempt) FROM attempts) AS complete
    """


def sample_facts(config, attempt):
    return f"""
        WITH RECURSIVE samples(sample) AS (
            SELECT 0 UNION ALL SELECT sample + 1 FROM samples WHERE sample + 1 < {config.t_samples}
        ) SELECT samples.sample,
          coalesce(max(CASE WHEN kind = 'run.json' THEN json_extract(content, '$.exit_code') >= 0 END), 0)
          OR coalesce(max(CASE WHEN kind = 'timeouts.txt' THEN length(content) - length(replace(content, char(10), '')) END), 0)
              >= {config.t_sample_retries + 1} AS has_solution,
          max(0, {config.t_sample_retries + 1} - coalesce(max(CASE WHEN kind = 'timeouts.txt' THEN length(content) - length(replace(content, char(10), '')) END), 0)) AS retries_left,
          coalesce(max(kind = 'tests.json'), 0) AS has_results
        FROM samples LEFT JOIN artifacts ON artifacts.sample = samples.sample AND attempt = {attempt}
        GROUP BY samples.sample
    """
