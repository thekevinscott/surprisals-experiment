SELECT CAST(substr(path, 10, instr(substr(path, 10), '/') - 1) AS INTEGER) AS attempt,
  max(CASE WHEN kind = 'metadata.json' THEN content ->> 'measurement' END) AS measurement,
  sum(kind = 'tests.json') = {samples} AS tested,
  sum(CASE WHEN kind = 'tests.json' THEN content ->> 'all_passed' ELSE 0 END) = {samples} AS passed
FROM (
  SELECT path, content, 'metadata.json' AS kind FROM './attempts/*/advices/0/metadata.json'
  UNION ALL
  SELECT path, content, 'tests.json' FROM './attempts/*/t_samples/*/tests.json'
) GROUP BY attempt
