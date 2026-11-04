WITH passing AS (
  SELECT ts.id, ts.advice_id
  FROM ts
  JOIN test_results ON test_results.t_id = ts.id
  GROUP BY ts.id
  HAVING min(test_results.passed) = 1
)
SELECT turns.id AS turn_id, turns.position AS turn, advice.text, advice.score, advice.score_text
FROM windows
JOIN forks ON forks.window_id = windows.id
JOIN turns ON turns.fork_id = forks.id
JOIN advice ON advice.turn_id = turns.id
JOIN passing ON passing.advice_id = advice.id
GROUP BY advice.id
HAVING count(*) = :samples
-- Ties go to the earliest turn.
ORDER BY advice.score, windows.position, turns.position, forks.position
LIMIT 1
