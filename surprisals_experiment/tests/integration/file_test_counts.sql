SELECT files.id, files.path, count(test_results.id) AS tests, sum(test_results.passed) AS passed
FROM files JOIN ts ON files.t_id = ts.id JOIN test_results ON test_results.t_id = ts.id
WHERE ts.advice_id = '0/0/1' GROUP BY files.id ORDER BY files.id
