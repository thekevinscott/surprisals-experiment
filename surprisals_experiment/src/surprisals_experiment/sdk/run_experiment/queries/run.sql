SELECT CASE
  WHEN EXISTS (SELECT 1 FROM stop_windows) THEN 'stopped'
  WHEN :cap >= 0 AND EXISTS (SELECT 1 FROM finished WHERE (window + 1) * 40 >= :cap) THEN 'stopped'
  WHEN NOT EXISTS (SELECT 1 FROM windows) THEN 'window_missing'
  WHEN EXISTS (SELECT 1 FROM finished WHERE window = (SELECT max(position) FROM windows)) THEN 'window_missing'
  WHEN EXISTS (
    SELECT 1 FROM expected LEFT JOIN complete USING (window, fork, turn)
    WHERE expected.window = (SELECT max(position) FROM windows) AND expected.turn < 10 AND complete.id IS NULL
  ) THEN 'fork_round'
  ELSE 'solo' END AS state,
  CASE WHEN NOT EXISTS (SELECT 1 FROM windows) THEN 0
       WHEN EXISTS (SELECT 1 FROM finished WHERE window = (SELECT max(position) FROM windows))
       THEN (SELECT max(position) + 1 FROM windows)
       ELSE (SELECT max(position) FROM windows) END AS window,
  coalesce((SELECT fork FROM winners ORDER BY window DESC LIMIT 1), 0) AS fork
