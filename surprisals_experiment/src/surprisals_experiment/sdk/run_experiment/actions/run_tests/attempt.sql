SELECT t_attempts.position AS attempt FROM windows
JOIN forks ON forks.window_id = windows.id AND forks.position = :fork
JOIN turns ON turns.fork_id = forks.id AND turns.position = :turn
JOIN t_attempts ON t_attempts.turn_id = turns.id AND t_attempts.sample = :sample AND t_attempts.exit_code != -1
WHERE windows.position = :window
