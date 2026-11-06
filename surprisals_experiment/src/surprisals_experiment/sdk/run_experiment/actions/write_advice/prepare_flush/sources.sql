SELECT ts.position, t_attempts.position AS attempt
FROM ts JOIN t_attempts ON t_attempts.t_id = ts.id AND t_attempts.exit_code != -1
WHERE ts.turn_id = :turn_id ORDER BY ts.position
