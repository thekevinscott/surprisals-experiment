SELECT turns.id IS NULL AS advice_missing
FROM (SELECT :turn AS position) requested
LEFT JOIN windows ON windows.position = :window
LEFT JOIN forks ON forks.window_id = windows.id AND forks.position = :fork
LEFT JOIN turns ON turns.fork_id = forks.id AND turns.position = requested.position
