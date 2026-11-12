SELECT turns.id AS turn_id, turns.position, advices.text
FROM windows
JOIN forks ON forks.window_id = windows.id AND forks.position = :fork
JOIN turns ON turns.fork_id = forks.id AND turns.position < :turn
JOIN turn_advice ON turn_advice.turn_id = turns.id
JOIN advices ON advices.id = turn_advice.advice_id
WHERE windows.position = :window
ORDER BY turns.position
