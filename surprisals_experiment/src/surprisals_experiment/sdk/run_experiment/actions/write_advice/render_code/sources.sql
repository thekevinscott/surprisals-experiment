SELECT ts.position, t_attempts.position AS attempt,
       coalesce(sum(test_results.passed), 0) AS passed, count(test_results.id) AS cases
FROM ts JOIN t_attempts ON t_attempts.turn_id = ts.turn_id AND t_attempts.sample = ts.position AND t_attempts.exit_code != -1
LEFT JOIN test_results ON test_results.t_id = ts.id
WHERE ts.turn_id = :turn_id GROUP BY ts.id ORDER BY ts.position
