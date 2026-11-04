SELECT windows.position AS window, forks.position AS fork, turns.position AS turn,
       advice.text, advice.score, advice.score_text, advice.rejected
FROM advice JOIN turns ON advice.turn_id = turns.id JOIN forks ON turns.fork_id = forks.id
JOIN windows ON forks.window_id = windows.id ORDER BY turns.position
