WITH attempts AS (
  SELECT CAST(substr(path, 25, instr(substr(path, 25), '/') - 1) AS INTEGER) AS attempt,
    max(CASE WHEN kind = 'metadata.json' THEN content ->> 'measurement' END) AS measurement,
    sum(kind = 'tests.json') = {samples} AS tested,
    sum(CASE WHEN kind = 'tests.json' THEN content ->> 'all_passed' ELSE 0 END) = {samples} AS passed
  FROM (
    SELECT path, content, 'metadata.json' AS kind FROM './windows/0/forks/0/turns/*/metadata.json'
    UNION ALL
    SELECT path, content, 'tests.json' FROM './windows/0/forks/0/turns/*/ts/*/tests.json'
  ) GROUP BY attempt
)
SELECT attempt, measurement FROM attempts
WHERE tested AND passed AND measurement IS NOT NULL
ORDER BY measurement, attempt LIMIT 1
