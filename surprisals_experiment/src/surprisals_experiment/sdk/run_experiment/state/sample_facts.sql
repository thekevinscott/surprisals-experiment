WITH RECURSIVE samples(sample) AS (
    SELECT 0 UNION ALL SELECT sample + 1 FROM samples WHERE sample + 1 < {samples}
) SELECT samples.sample,
  coalesce(max(CASE WHEN kind = 'run.json' THEN json_extract(content, '$.exit_code') >= 0 END), 0)
  OR coalesce(max(CASE WHEN kind = 'timeouts.txt' THEN length(content) - length(replace(content, char(10), '')) END), 0)
      >= {tries} AS has_solution,
  coalesce(max(kind = 'tests.json'), 0) AS has_results
FROM samples LEFT JOIN artifacts ON artifacts.sample = samples.sample AND attempt = {attempt}
GROUP BY samples.sample
