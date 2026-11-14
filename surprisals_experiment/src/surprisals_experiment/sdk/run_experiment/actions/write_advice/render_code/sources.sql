WITH latest AS (
  SELECT sample, max(position) AS attempt, count(*) AS attempts
  FROM t_attempts WHERE turn_id = :turn_id GROUP BY sample
)
SELECT latest.sample AS position, latest.attempt, latest.attempts, t_attempts.timed_out,
       coalesce(sum(test_results.passed), 0) AS passed, count(test_results.id) AS cases
FROM latest JOIN t_attempts ON t_attempts.turn_id = :turn_id
  AND t_attempts.sample = latest.sample AND t_attempts.position = latest.attempt
LEFT JOIN ts ON ts.turn_id = :turn_id AND ts.position = latest.sample
LEFT JOIN test_results ON test_results.t_id = ts.id
WHERE t_attempts.exit_code != -1 OR t_attempts.timed_out
GROUP BY latest.sample ORDER BY latest.sample
