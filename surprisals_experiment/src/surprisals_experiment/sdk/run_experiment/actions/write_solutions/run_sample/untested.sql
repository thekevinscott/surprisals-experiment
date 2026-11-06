SELECT EXISTS (
  SELECT 1 FROM windows
  JOIN forks ON forks.window_id = windows.id AND forks.position = :fork
  JOIN turns ON turns.fork_id = forks.id AND turns.position = :turn
  JOIN ts ON ts.turn_id = turns.id AND ts.position = :sample
  LEFT JOIN test_results ON test_results.t_id = ts.id
  WHERE windows.position = :window AND test_results.id IS NULL
) AS missing
