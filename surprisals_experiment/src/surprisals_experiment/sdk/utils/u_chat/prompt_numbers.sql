SELECT :window AS window, :turn + 1 AS turn, 40 AS turns,
       min(score) AS start_best, min(score) * 0.95 AS target
FROM complete_turns
WHERE passed = 1 AND samples = :samples AND window < :window
