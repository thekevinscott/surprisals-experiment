WITH fork_turns AS (
  SELECT turns.position,
         turn_advice.turn_id IS NULL OR advices.score IS NOT NULL AND coalesce(evaluated_turns.samples, 0) + coalesce(exhausted.samples, 0) >= :samples AS done
  FROM windows
  JOIN forks ON forks.window_id = windows.id AND forks.position = :fork
  JOIN turns ON turns.fork_id = forks.id
  LEFT JOIN turn_advice ON turn_advice.turn_id = turns.id
  LEFT JOIN advices ON advices.id = turn_advice.advice_id
  LEFT JOIN evaluated_turns ON evaluated_turns.id = turns.id
  LEFT JOIN (SELECT turn_id, count(*) AS samples FROM (
    SELECT turn_id FROM t_attempts WHERE timed_out GROUP BY turn_id, sample HAVING count(*) >= :timeouts
  ) GROUP BY turn_id) AS exhausted ON exhausted.turn_id = turns.id
  WHERE windows.position = :window
)
SELECT coalesce((SELECT max(position) FROM fork_turns), -1) AS latest,
       coalesce((SELECT NOT done FROM fork_turns ORDER BY position DESC LIMIT 1), 0) AS pending,
       (SELECT count(*) FROM fork_turns WHERE done) AS completed,
       (SELECT count(*) FROM fork_turns) AS turns
