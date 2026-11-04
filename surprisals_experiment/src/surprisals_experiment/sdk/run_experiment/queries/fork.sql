SELECT CASE
  WHEN turns.id IS NULL THEN 'advice_missing'
  WHEN advices.score IS NULL THEN 'unscored'
  WHEN EXISTS (
    SELECT 1 FROM samples
    WHERE NOT EXISTS (SELECT 1 FROM generations WHERE generations.turn_id = turns.id AND generations.position = samples.position)
      AND NOT EXISTS (SELECT 1 FROM ts WHERE ts.turn_id = turns.id AND ts.position = samples.position)
  ) THEN 'solutions_missing'
  WHEN EXISTS (SELECT 1 FROM samples WHERE NOT EXISTS (
    SELECT 1 FROM ts WHERE ts.turn_id = turns.id AND ts.position = samples.position
  )) THEN 'untested'
  ELSE 'feedback_missing' END AS state, expected.turn
FROM expected
LEFT JOIN forks ON forks.position = expected.fork AND forks.window_id = (SELECT id FROM windows WHERE position = expected.window)
LEFT JOIN turns ON turns.fork_id = forks.id AND turns.position = expected.turn
LEFT JOIN turn_advice ON turn_advice.turn_id = turns.id
LEFT JOIN advices ON advices.id = turn_advice.advice_id
LEFT JOIN complete ON complete.id = turns.id
WHERE expected.window = :window AND expected.fork = :fork
  AND (expected.turn < 10 OR :turn >= 10) AND complete.id IS NULL
ORDER BY expected.turn LIMIT 1
