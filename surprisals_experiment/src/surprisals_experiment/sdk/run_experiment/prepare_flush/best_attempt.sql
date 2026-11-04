SELECT metadata.dir, metadata.content ->> 'measurement' AS measurement,
  metadata.content -> 'tokens' AS tokens, advice.content AS advice
FROM './windows/*/forks/*/turns/*/metadata.json' AS metadata
JOIN './windows/*/forks/*/turns/*/advice.txt' AS advice ON advice.dir = metadata.dir
JOIN './windows/*/forks/*/turns/*/ts/*/tests.json' AS tests ON tests.dir LIKE metadata.dir || '/ts/%'
GROUP BY metadata.dir, metadata.content, advice.content
HAVING count(*) = {samples} AND min(tests.content ->> 'all_passed')
-- Ties go to the earliest turn. CAST reads the leading digits after each segment.
ORDER BY measurement,
  CAST(substr(metadata.dir, instr(metadata.dir, 'windows/') + 8) AS INTEGER),
  CAST(substr(metadata.dir, instr(metadata.dir, '/turns/') + 7) AS INTEGER),
  CAST(substr(metadata.dir, instr(metadata.dir, '/forks/') + 7) AS INTEGER)
LIMIT 1
