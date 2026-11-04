-- Earlier state checks handle advice, solutions, and tests.
SELECT NOT EXISTS (
  SELECT 1 FROM windows
  JOIN forks ON forks.window_id = windows.id
  JOIN turns ON turns.fork_id = forks.id
  JOIN feedback ON feedback.turn_id = turns.id
  WHERE windows.position = :window AND forks.position = :fork AND turns.position = :turn
) AS feedback_missing
