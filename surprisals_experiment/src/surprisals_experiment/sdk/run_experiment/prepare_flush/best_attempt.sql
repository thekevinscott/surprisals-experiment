SELECT id AS turn_id, turn, text, score, score_text
FROM complete
WHERE passed = 1 AND (window < :window OR (window = :window AND (:turn >= 10 OR fork = :fork)))
ORDER BY score, window, turn, fork LIMIT 1
