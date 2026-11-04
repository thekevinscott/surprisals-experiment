SELECT turn_advice.advice_id
FROM windows JOIN forks ON forks.window_id = windows.id
JOIN turns ON turns.fork_id = forks.id JOIN turn_advice ON turn_advice.turn_id = turns.id
WHERE windows.position = :window AND forks.position = :fork AND turns.position = :turn
