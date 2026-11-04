SELECT turn_id, score
FROM advice
WHERE text = {advice}
LIMIT 1
