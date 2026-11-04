SELECT CASE
  WHEN NOT EXISTS (
    SELECT 1 FROM windows JOIN forks ON forks.window_id = windows.id
    WHERE windows.position = 0 AND forks.position = 0
  ) THEN 'not_started'
  -- Finish a partially published turn before evaluating stopping budgets.
  WHEN EXISTS (
    SELECT 1 FROM run_turns LEFT JOIN run_complete USING (id)
    WHERE run_complete.id IS NULL
  ) THEN 'turn'
  WHEN :cap >= 0 AND (SELECT count(*) FROM run_complete) >= :cap THEN 'stopped'
  WHEN (SELECT count(*) FROM run_complete
        WHERE turn > coalesce((SELECT max(turn) FROM improvements), -1)) >= :max_stale THEN 'stopped'
  ELSE 'turn' END AS state,
  (SELECT turn FROM next_turn) AS turn
