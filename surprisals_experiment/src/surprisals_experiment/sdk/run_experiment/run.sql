WITH RECURSIVE run_turns AS (
  SELECT turns.id, turns.position AS turn
  FROM windows JOIN forks ON forks.window_id = windows.id
  JOIN turns ON turns.fork_id = forks.id
  WHERE windows.position = 0 AND forks.position = 0
), completed AS (
  SELECT * FROM complete_turns WHERE window = 0 AND fork = 0 AND samples = :samples
), positions(turn) AS (
  SELECT 0 UNION ALL SELECT turn + 1 FROM positions
  WHERE turn <= coalesce((SELECT max(turn) FROM run_turns), -1)
)
SELECT CASE
  WHEN NOT EXISTS (
    SELECT 1 FROM windows JOIN forks ON forks.window_id = windows.id
    WHERE windows.position = 0 AND forks.position = 0
  ) THEN 'not_started'
  WHEN EXISTS (
    SELECT 1 FROM run_turns LEFT JOIN completed USING (id) WHERE completed.id IS NULL
  ) THEN 'turn'
  WHEN :cap >= 0 AND (SELECT count(*) FROM completed) >= :cap THEN 'stopped'
  ELSE 'turn' END AS state,
  (SELECT min(turn) FROM positions
   WHERE NOT EXISTS (SELECT 1 FROM completed WHERE completed.turn = positions.turn)) AS turn
