SELECT id AS turn_id, turn, text, score, score_text
FROM evaluated_turns WHERE passed = 1 AND samples = :samples
ORDER BY score, window, turn, fork LIMIT 1
