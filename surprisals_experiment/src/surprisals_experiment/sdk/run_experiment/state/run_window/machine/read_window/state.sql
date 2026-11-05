SELECT coalesce((
  SELECT fork FROM evaluated_turns
  WHERE window = :window AND passed = 1 AND samples = :samples
  ORDER BY score, fork, turn LIMIT 1
), 0) AS winner
