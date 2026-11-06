WITH best AS (
  SELECT id, turn, text, score, score_text
  FROM evaluated_turns WHERE passed = 1 AND samples = :samples AND score IS NOT NULL
  ORDER BY score, window, turn, fork LIMIT 1
)
SELECT ts.id AS t_id, turn, text, score, score_text
FROM best JOIN ts ON ts.turn_id = best.id
ORDER BY ts.position
