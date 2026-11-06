SELECT ts.id FROM windows
JOIN forks ON forks.window_id = windows.id AND forks.position = :fork
JOIN turns ON turns.fork_id = forks.id AND turns.position = :turn
JOIN ts ON ts.turn_id = turns.id AND ts.position = :sample
WHERE windows.position = :window
