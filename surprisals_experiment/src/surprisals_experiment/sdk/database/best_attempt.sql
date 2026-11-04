SELECT metadata.dir, metadata.content ->> 'measurement' AS measurement
FROM './windows/0/forks/0/turns/*/metadata.json' AS metadata
JOIN './windows/0/forks/0/turns/*/ts/*/tests.json' AS tests ON tests.dir LIKE metadata.dir || '/ts/%'
GROUP BY metadata.dir
HAVING count(*) = {samples} AND min(tests.content ->> 'all_passed')
-- Ties go to the earliest turn: shorter dir, then lexical, is numeric order.
ORDER BY measurement, length(metadata.dir), metadata.dir
LIMIT 1
