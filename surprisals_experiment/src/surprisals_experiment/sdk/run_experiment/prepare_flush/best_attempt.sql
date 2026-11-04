WITH passing AS (
  SELECT ts.id, ts.turn_id
  FROM ts
  JOIN test_results ON test_results.t_id = ts.id
  GROUP BY ts.id
  HAVING min(test_results.passed) = 1
)
SELECT turns.id AS turn_id, turns.position AS turn, advices.text, advices.score, advices.score_text
FROM windows
JOIN forks ON forks.window_id = windows.id
JOIN turns ON turns.fork_id = forks.id
JOIN turn_advice ON turn_advice.turn_id = turns.id
JOIN advices ON advices.id = turn_advice.advice_id
JOIN passing ON passing.turn_id = turns.id
GROUP BY turns.id
HAVING count(*) = :samples
-- Ties go to the earliest turn.
ORDER BY advices.score, windows.position, turns.position, forks.position
LIMIT 1
