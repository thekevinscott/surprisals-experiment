SELECT samples.position,
       CASE WHEN generations.id IS NULL THEN 'solutions_missing'
            WHEN ts.id IS NULL THEN 'untested' ELSE 'complete' END AS state
FROM samples
JOIN windows ON windows.position = :window
JOIN forks ON forks.window_id = windows.id AND forks.position = :fork
JOIN turns ON turns.fork_id = forks.id AND turns.position = :turn
LEFT JOIN generations ON generations.turn_id = turns.id AND generations.position = samples.position
LEFT JOIN ts ON ts.turn_id = turns.id AND ts.position = samples.position
ORDER BY samples.position
