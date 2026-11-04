WITH RECURSIVE samples(position) AS (
  SELECT 0 UNION ALL SELECT position + 1 FROM samples WHERE position + 1 < :samples
)
SELECT EXISTS (
  SELECT 1
  FROM windows
  JOIN forks ON forks.window_id = windows.id AND forks.position = :fork
  JOIN turns ON turns.fork_id = forks.id AND turns.position = :turn
  JOIN turn_advice ON turn_advice.turn_id = turns.id
  JOIN advices ON advices.id = turn_advice.advice_id
  WHERE windows.position = :window AND advices.score IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM samples WHERE NOT EXISTS (
        SELECT 1 FROM ts
        WHERE ts.turn_id = turns.id AND ts.position = samples.position
      )
    )
) AS solutions_missing
