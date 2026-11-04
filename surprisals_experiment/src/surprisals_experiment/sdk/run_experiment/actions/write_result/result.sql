WITH completed AS (
  SELECT * FROM evaluated_turns
  WHERE window = :window AND fork = :fork AND turn <= :turn AND samples = :samples
), improvements AS (
  SELECT current.turn FROM completed current
  WHERE current.passed = 1 AND NOT EXISTS (
    SELECT 1 FROM completed previous
    WHERE previous.turn < current.turn AND previous.passed = 1 AND previous.score <= current.score
  )
)
SELECT (SELECT score FROM completed WHERE passed = 1 ORDER BY score, turn LIMIT 1) AS score,
       (SELECT id FROM completed WHERE passed = 1 ORDER BY score, turn LIMIT 1) AS turn_id,
       :turn + 1 AS attempts,
       (SELECT count(*) FROM completed WHERE turn > coalesce((SELECT max(turn) FROM improvements), -1)) AS stale
