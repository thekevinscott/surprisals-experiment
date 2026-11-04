SELECT :window AS window, :turn + 1 AS turn, 40 AS turns,
       min(score) AS start_best,
       CASE WHEN :strategy = 'characters' THEN cast(min(score) * 0.95 AS INTEGER)
            ELSE min(score) * 0.95 END AS target
FROM complete_turns
WHERE passed = 1 AND samples = :samples AND window < :window
