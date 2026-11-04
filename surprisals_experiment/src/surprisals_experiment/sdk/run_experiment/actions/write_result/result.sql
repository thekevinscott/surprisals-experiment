SELECT (SELECT score FROM run_complete WHERE passed = 1 ORDER BY score, turn LIMIT 1) AS score,
       (SELECT id FROM run_complete WHERE passed = 1 ORDER BY score, turn LIMIT 1) AS turn_id,
       (SELECT count(*) FROM run_complete) AS attempts
