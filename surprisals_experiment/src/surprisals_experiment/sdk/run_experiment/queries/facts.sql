WITH RECURSIVE
samples(position) AS (
  SELECT 0 UNION ALL SELECT position + 1 FROM samples WHERE position + 1 < :samples
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
  JOIN generations ON generations.turn_id = turns.id AND generations.position = tested.position
  WHERE advices.score IS NOT NULL AND tested.position >= 0 AND tested.position < :samples
  GROUP BY turns.id HAVING count(*) = :samples
),
complete AS (
  SELECT ready.* FROM ready JOIN feedback ON feedback.turn_id = ready.id
),
run_turns AS (
  SELECT turns.id, turns.position AS turn
  FROM windows JOIN forks ON forks.window_id = windows.id
  JOIN turns ON turns.fork_id = forks.id
  WHERE windows.position = 0 AND forks.position = 0
),
run_complete AS (
  SELECT * FROM complete WHERE window = 0 AND fork = 0
),
improvements AS (
  SELECT current.turn FROM run_complete current
  WHERE current.passed = 1 AND NOT EXISTS (
    SELECT 1 FROM run_complete previous
    WHERE previous.turn < current.turn AND previous.passed = 1 AND previous.score <= current.score
  )
),
positions(turn) AS (
  SELECT 0 UNION ALL SELECT turn + 1 FROM positions
  WHERE turn <= coalesce((SELECT max(turn) FROM run_turns), -1)
),
next_turn AS (
  SELECT min(turn) AS turn FROM positions
  WHERE NOT EXISTS (SELECT 1 FROM run_complete WHERE run_complete.turn = positions.turn)
)
