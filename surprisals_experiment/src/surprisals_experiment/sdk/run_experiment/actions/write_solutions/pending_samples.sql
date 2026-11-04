WITH RECURSIVE samples(position) AS (
  SELECT 0 UNION ALL SELECT position + 1 FROM samples WHERE position + 1 < :samples
)
SELECT samples.position FROM samples
JOIN windows ON windows.position = :window
JOIN forks ON forks.window_id = windows.id AND forks.position = :fork
JOIN turns ON turns.fork_id = forks.id AND turns.position = :turn
WHERE NOT EXISTS (
  SELECT 1 FROM generations WHERE generations.turn_id = turns.id AND generations.position = samples.position
)
ORDER BY samples.position
