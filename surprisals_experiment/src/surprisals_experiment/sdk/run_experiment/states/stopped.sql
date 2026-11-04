WITH run_turns AS (
  SELECT turns.id, turns.position AS turn
  FROM windows JOIN forks ON forks.window_id = windows.id
  JOIN turns ON turns.fork_id = forks.id
  WHERE windows.position = 0 AND forks.position = 0
), completed AS (
  SELECT * FROM complete_turns WHERE window = 0 AND fork = 0 AND samples = :samples
), improvements AS (
  SELECT current.turn FROM completed current
  WHERE current.passed = 1 AND NOT EXISTS (
    SELECT 1 FROM completed previous
    WHERE previous.turn < current.turn AND previous.passed = 1 AND previous.score <= current.score
  )
)
SELECT EXISTS (
  SELECT 1 FROM windows JOIN forks ON forks.window_id = windows.id
  WHERE windows.position = 0 AND forks.position = 0
) AND NOT EXISTS (
  SELECT 1 FROM run_turns LEFT JOIN completed USING (id) WHERE completed.id IS NULL
) AND (
  (:cap >= 0 AND (SELECT count(*) FROM completed) >= :cap)
  OR (SELECT count(*) FROM completed
      WHERE turn > coalesce((SELECT max(turn) FROM improvements), -1)) >= :max_stale
) AS stopped;
