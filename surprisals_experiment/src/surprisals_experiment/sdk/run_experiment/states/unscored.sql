SELECT EXISTS (
  SELECT 1
  FROM windows
  JOIN forks ON forks.window_id = windows.id AND forks.position = :fork
  JOIN turns ON turns.fork_id = forks.id AND turns.position = :turn
  LEFT JOIN turn_advice ON turn_advice.turn_id = turns.id
  LEFT JOIN advices ON advices.id = turn_advice.advice_id
  WHERE windows.position = :window AND advices.score IS NULL
) AS unscored
