-- Earlier state checks handle missing advice and solutions.
WITH RECURSIVE samples(position) AS (
  SELECT 0 UNION ALL SELECT position + 1 FROM samples WHERE position + 1 < :samples
)
SELECT EXISTS (
  SELECT 1 FROM samples WHERE NOT EXISTS (
    SELECT 1 FROM windows
    JOIN forks ON forks.window_id = windows.id
    JOIN turns ON turns.fork_id = forks.id
    JOIN ts ON ts.turn_id = turns.id
    WHERE windows.position = :window AND forks.position = :fork
      AND turns.position = :turn AND ts.position = samples.position
  )
) AS untested
