SELECT ts.position, t_attempts.position AS attempt, 0 AS attempts, 0 AS timed_out,
       coalesce(sum(test_results.passed), 0) AS passed, count(test_results.id) AS cases
FROM ts JOIN t_attempts ON t_attempts.turn_id = ts.turn_id AND t_attempts.sample = ts.position AND t_attempts.exit_code != -1
LEFT JOIN test_results ON test_results.t_id = ts.id
WHERE ts.turn_id = :turn_id GROUP BY ts.id
UNION ALL
SELECT sample AS position, max(position) AS attempt, count(*) AS attempts, 1 AS timed_out,
       0 AS passed, 0 AS cases
FROM t_attempts WHERE turn_id = :turn_id
GROUP BY sample HAVING min(timed_out) = 1
ORDER BY position
