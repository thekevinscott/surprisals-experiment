SELECT id AS turn_id, turn, text, score, score_text
FROM complete
WHERE passed = 1
ORDER BY score, window, turn, fork LIMIT 1
