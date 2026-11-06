WITH exhausted AS (
  SELECT turn_id, count(*) AS samples FROM (
    SELECT turn_id FROM t_timeouts GROUP BY turn_id, position HAVING count(*) >= :timeouts
  ) GROUP BY turn_id
), completed AS (
  SELECT * FROM evaluated_turns
  WHERE samples = :samples AND score IS NOT NULL
), best AS (
  SELECT * FROM completed WHERE passed = 1 ORDER BY score, window, turn, fork LIMIT 1
)
SELECT (SELECT score FROM best) AS score,
       (SELECT id FROM best) AS turn_id,
       (SELECT t_attempts.position FROM best JOIN ts ON ts.turn_id = best.id AND ts.position = 0
        JOIN t_attempts ON t_attempts.t_id = ts.id AND t_attempts.exit_code != -1) AS attempt,
       (SELECT count(*) FROM turns
        JOIN turn_advice ON turn_advice.turn_id = turns.id
        JOIN advices ON advices.id = turn_advice.advice_id AND advices.score IS NOT NULL
        LEFT JOIN evaluated_turns ON evaluated_turns.id = turns.id
        LEFT JOIN exhausted ON exhausted.turn_id = turns.id
        WHERE coalesce(evaluated_turns.samples, 0) + coalesce(exhausted.samples, 0) >= :samples) AS attempts
