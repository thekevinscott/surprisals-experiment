SELECT id AS turn_id, turn, text, score, score_text
FROM ready_turns WHERE passed = 1 AND samples = :samples
  AND (window < :window OR (window = :window AND turn < :cutoff
       AND (:cutoff > 10 OR fork = :fork)))
ORDER BY score, window, turn, fork LIMIT 1
