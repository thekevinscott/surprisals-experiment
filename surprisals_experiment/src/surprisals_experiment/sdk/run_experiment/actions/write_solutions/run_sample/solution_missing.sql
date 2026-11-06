SELECT NOT EXISTS (
  SELECT 1 FROM windows
  JOIN forks ON forks.window_id = windows.id AND forks.position = :fork
  JOIN turns ON turns.fork_id = forks.id AND turns.position = :turn
  JOIN ts ON ts.turn_id = turns.id AND ts.position = :sample
  WHERE windows.position = :window
) AND (
  SELECT count(*) FROM windows
  JOIN forks ON forks.window_id = windows.id AND forks.position = :fork
  JOIN turns ON turns.fork_id = forks.id AND turns.position = :turn
  JOIN t_attempts ON t_attempts.turn_id = turns.id AND t_attempts.sample = :sample AND t_attempts.timed_out
  WHERE windows.position = :window
) < :timeouts AS missing
