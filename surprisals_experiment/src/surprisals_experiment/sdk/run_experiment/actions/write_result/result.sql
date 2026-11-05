WITH completed AS (
  SELECT * FROM evaluated_turns
  WHERE samples = :samples AND score IS NOT NULL
)
SELECT (SELECT score FROM completed WHERE passed = 1 ORDER BY score, window, turn, fork LIMIT 1) AS score,
       (SELECT id FROM completed WHERE passed = 1 ORDER BY score, window, turn, fork LIMIT 1) AS turn_id,
       (SELECT count(*) FROM completed) AS attempts
