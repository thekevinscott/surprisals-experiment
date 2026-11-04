SELECT sum(test_results.passed) AS passed, count(*) AS total, min(test_results.passed) AS all_passed
FROM windows
JOIN forks ON forks.window_id = windows.id
JOIN turns ON turns.fork_id = forks.id
JOIN ts ON ts.turn_id = turns.id
JOIN test_results ON test_results.t_id = ts.id
WHERE windows.position = :window AND forks.position = :fork AND turns.position = :turn
GROUP BY ts.id
ORDER BY ts.position
