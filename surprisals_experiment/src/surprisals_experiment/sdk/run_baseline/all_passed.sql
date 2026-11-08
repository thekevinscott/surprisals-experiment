SELECT count(*) AS all_passed FROM (
  SELECT ts.id FROM ts JOIN test_results ON test_results.t_id = ts.id
  GROUP BY ts.id HAVING min(test_results.passed) = 1
)
