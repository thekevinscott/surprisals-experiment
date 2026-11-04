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
