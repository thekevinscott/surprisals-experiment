SELECT NOT EXISTS (
  SELECT 1 FROM windows
  JOIN forks ON forks.window_id = windows.id AND forks.position = :fork
  JOIN turns ON turns.fork_id = forks.id AND turns.position = :turn
  JOIN generations ON generations.turn_id = turns.id AND generations.position = :sample
  WHERE windows.position = :window
) AS missing
