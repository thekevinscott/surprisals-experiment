WITH current_turn AS (
  SELECT turns.id, advices.score
  FROM windows
  JOIN forks ON forks.window_id = windows.id AND forks.position = :fork
  JOIN turns ON turns.fork_id = forks.id AND turns.position = :turn
  JOIN turn_advice ON turn_advice.turn_id = turns.id
  JOIN advices ON advices.id = turn_advice.advice_id
  WHERE windows.position = :window
)
SELECT CASE
  WHEN NOT EXISTS (SELECT 1 FROM current_turn) THEN 'advice_missing'
  WHEN (SELECT score FROM current_turn) IS NULL THEN 'unscored'
  WHEN coalesce((SELECT samples FROM evaluated_turns
                 WHERE id = (SELECT id FROM current_turn)), 0)
       + (SELECT count(*) FROM (SELECT position FROM t_timeouts
            WHERE turn_id = (SELECT id FROM current_turn)
            GROUP BY position HAVING count(*) >= :timeouts)) < :samples
    THEN 'solutions_missing'
  ELSE 'turn_done'
END AS state
