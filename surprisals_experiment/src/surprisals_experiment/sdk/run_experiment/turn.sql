WITH RECURSIVE samples(position) AS (
  SELECT 0 UNION ALL SELECT position + 1 FROM samples WHERE position + 1 < :samples
)
SELECT CASE
  WHEN turns.id IS NULL THEN 'advice_missing'
  WHEN advices.score IS NULL THEN 'unscored'
  WHEN EXISTS (
    SELECT 1 FROM samples WHERE NOT EXISTS (
      SELECT 1 FROM generations WHERE generations.turn_id = turns.id AND generations.position = samples.position
    )
  ) THEN 'solutions_missing'
  WHEN EXISTS (
    SELECT 1 FROM samples WHERE NOT EXISTS (
      SELECT 1 FROM ts WHERE ts.turn_id = turns.id AND ts.position = samples.position
    )
  ) THEN 'untested'
  WHEN feedback.turn_id IS NULL THEN 'feedback_missing'
  ELSE 'complete' END AS state
FROM (SELECT :turn AS position) requested
LEFT JOIN windows ON windows.position = :window
LEFT JOIN forks ON forks.window_id = windows.id AND forks.position = :fork
LEFT JOIN turns ON turns.fork_id = forks.id AND turns.position = requested.position
LEFT JOIN turn_advice ON turn_advice.turn_id = turns.id
LEFT JOIN advices ON advices.id = turn_advice.advice_id
LEFT JOIN feedback ON feedback.turn_id = turns.id
