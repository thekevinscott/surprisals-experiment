SELECT NOT EXISTS (
  SELECT 1 FROM windows JOIN forks ON forks.window_id = windows.id
  WHERE windows.position = 0 AND forks.position = 0
) AS not_started
