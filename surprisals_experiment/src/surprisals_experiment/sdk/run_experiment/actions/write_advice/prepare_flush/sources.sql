SELECT ts.position, t_attempts.position AS attempt
FROM ts JOIN t_attempts ON t_attempts.turn_id = ts.turn_id AND t_attempts.sample = ts.position AND t_attempts.exit_code != -1
WHERE ts.turn_id = :turn_id ORDER BY ts.position
