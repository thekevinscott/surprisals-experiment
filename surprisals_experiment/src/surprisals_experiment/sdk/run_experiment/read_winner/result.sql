WITH latest_window AS (
  SELECT coalesce(max(position), 0) AS position FROM windows
), winner AS (
  SELECT coalesce((SELECT fork FROM evaluated_turns
    WHERE window = (SELECT position FROM latest_window) AND passed = 1 AND samples = :samples
    ORDER BY score, fork, turn LIMIT 1), 0) AS position
)
SELECT latest_window.position AS window, winner.position AS fork,
       coalesce((SELECT max(turns.position) FROM turns
         JOIN forks ON turns.fork_id = forks.id
         JOIN windows ON forks.window_id = windows.id
         WHERE windows.position = latest_window.position AND forks.position = winner.position), -1) AS turn
FROM latest_window, winner
