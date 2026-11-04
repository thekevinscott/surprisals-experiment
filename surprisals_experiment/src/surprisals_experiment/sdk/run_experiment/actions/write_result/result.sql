SELECT (SELECT score FROM complete WHERE passed = 1 ORDER BY score, window, turn, fork LIMIT 1) AS score,
       (SELECT id FROM complete WHERE passed = 1 ORDER BY score, window, turn, fork LIMIT 1) AS turn_id,
       (SELECT count(*) FROM (
          SELECT window, turn FROM complete GROUP BY window, turn
       )) AS attempts
