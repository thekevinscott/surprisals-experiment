WITH completed AS (
  SELECT * FROM complete_turns WHERE samples = :samples
), best AS (
  SELECT id, score, window * 40 + turn AS time FROM completed WHERE passed = 1
  ORDER BY score, window, turn, fork LIMIT 1
)
SELECT (SELECT score FROM best) AS score,
       (SELECT id FROM best) AS turn_id,
       coalesce((SELECT max(window * 40 + turn) + 1 FROM completed), 0) AS attempts,
       coalesce((SELECT max(window * 40 + turn) FROM completed), -1) + 1
         - coalesce((SELECT time FROM best) + 1, 0) AS stale
