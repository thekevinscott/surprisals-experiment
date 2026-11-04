WITH RECURSIVE
fork_positions(position) AS (VALUES (0), (1), (2), (3)),
turn_positions(position) AS (
  SELECT 0 UNION ALL SELECT position + 1 FROM turn_positions WHERE position < 39
),
latest AS (SELECT max(position) AS window FROM windows),
complete AS (SELECT * FROM complete_turns WHERE samples = :samples),
winner AS (
  SELECT coalesce((
    SELECT fork FROM complete WHERE window = (SELECT window FROM latest)
      AND turn < 10 AND passed = 1
    ORDER BY score, fork, turn LIMIT 1
  ), 0) AS fork
),
expected AS (
  SELECT turn_positions.position AS turn, fork_positions.position AS fork
  FROM turn_positions CROSS JOIN fork_positions
  WHERE (turn_positions.position < 10 OR fork_positions.position = (SELECT fork FROM winner))
    AND (:cap < 0 OR (SELECT window FROM latest) * 40 + turn_positions.position < :cap)
),
missing AS (
  SELECT expected.turn, expected.fork FROM expected
  WHERE NOT EXISTS (
    SELECT 1 FROM complete WHERE complete.window = (SELECT window FROM latest)
      AND complete.fork = expected.fork AND complete.turn = expected.turn
  )
),
progress AS (
  SELECT (SELECT window FROM latest) * 40 + coalesce((SELECT max(turn) FROM expected), -1) + 1 AS elapsed
),
best AS (
  SELECT window * 40 + turn AS time FROM complete WHERE passed = 1
  ORDER BY score, window, turn, fork LIMIT 1
)
SELECT CASE
  WHEN (SELECT window FROM latest) IS NULL THEN 'window_missing'
  WHEN NOT EXISTS (SELECT 1 FROM missing) AND :cap >= 0
       AND (SELECT elapsed FROM progress) >= :cap THEN 'stopped'
  WHEN NOT EXISTS (SELECT 1 FROM missing) AND
       (SELECT elapsed FROM progress) - coalesce((SELECT time FROM best), 0) >= :max_stale THEN 'stopped'
  WHEN NOT EXISTS (SELECT 1 FROM missing) THEN 'window_missing'
  WHEN EXISTS (SELECT 1 FROM missing WHERE turn < 10) THEN 'fork_round'
  ELSE 'solo' END AS state,
  CASE WHEN (SELECT window FROM latest) IS NULL THEN 0
       WHEN NOT EXISTS (SELECT 1 FROM missing) THEN (SELECT window + 1 FROM latest)
       ELSE (SELECT window FROM latest) END AS window,
  (SELECT fork FROM winner) AS fork
