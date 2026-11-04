WITH RECURSIVE
samples(position) AS (
  SELECT 0 UNION ALL SELECT position + 1 FROM samples WHERE position + 1 < :samples
),
fork_positions(position) AS (VALUES (0), (1), (2), (3)),
turn_positions(position) AS (
  SELECT 0 UNION ALL SELECT position + 1 FROM turn_positions WHERE position < 39
),
tested AS (
  SELECT ts.turn_id, ts.position, coalesce(min(test_results.passed), 0) AS passed
  FROM ts LEFT JOIN test_results ON test_results.t_id = ts.id
  GROUP BY ts.id
),
ready AS (
  SELECT turns.id, windows.position AS window, forks.position AS fork,
         turns.position AS turn, advices.text, advices.score, advices.score_text,
         min(tested.passed) AS passed
  FROM windows JOIN forks ON forks.window_id = windows.id
  JOIN turns ON turns.fork_id = forks.id
  JOIN turn_advice ON turn_advice.turn_id = turns.id
  JOIN advices ON advices.id = turn_advice.advice_id
  JOIN tested ON tested.turn_id = turns.id
  WHERE advices.score IS NOT NULL AND tested.position >= 0 AND tested.position < :samples
  GROUP BY turns.id HAVING count(*) = :samples
),
complete AS (
  SELECT ready.* FROM ready JOIN feedback ON feedback.turn_id = ready.id
),
round_winners AS (
  SELECT window, fork, row_number() OVER (PARTITION BY window ORDER BY score, fork, turn) AS rank
  FROM complete WHERE turn < 10 AND passed = 1
),
winners AS (
  SELECT windows.position AS window, coalesce(round_winners.fork, 0) AS fork
  FROM windows LEFT JOIN round_winners ON round_winners.window = windows.position AND rank = 1
),
expected AS (
  SELECT windows.position AS window, fork_positions.position AS fork, turn_positions.position AS turn
  FROM windows CROSS JOIN fork_positions CROSS JOIN turn_positions
  JOIN winners ON winners.window = windows.position
  WHERE (turn_positions.position < 10 OR fork_positions.position = winners.fork)
    AND (:cap < 0 OR windows.position * 40 + turn_positions.position < :cap)
),
finished AS (
  SELECT windows.position AS window FROM windows
  WHERE NOT EXISTS (
    SELECT 1 FROM expected LEFT JOIN complete USING (window, fork, turn)
    WHERE expected.window = windows.position AND complete.id IS NULL
  )
),
window_bests AS (
  SELECT windows.position AS window, min(complete.score) AS score
  FROM windows LEFT JOIN complete ON complete.window <= windows.position AND complete.passed = 1
  GROUP BY windows.id
),
stop_windows AS (
  SELECT finished.window FROM finished
  JOIN window_bests current ON current.window = finished.window
  JOIN window_bests previous ON previous.window = finished.window - 1
  WHERE current.score IS NULL OR (previous.score IS NOT NULL AND current.score > previous.score * 0.95)
     OR previous.score = 0
)
