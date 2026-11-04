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
LEFT JOIN run_turns turns ON turns.turn = requested.position
LEFT JOIN turn_advice ON turn_advice.turn_id = turns.id
LEFT JOIN advices ON advices.id = turn_advice.advice_id
LEFT JOIN feedback ON feedback.turn_id = turns.id
