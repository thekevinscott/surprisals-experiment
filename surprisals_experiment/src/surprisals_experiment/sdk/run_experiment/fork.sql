WITH RECURSIVE positions(turn) AS (
  SELECT :start UNION ALL SELECT turn + 1 FROM positions WHERE turn + 1 < :end
)
SELECT positions.turn FROM positions
WHERE NOT EXISTS (
  SELECT 1 FROM complete_turns
  WHERE window = :window AND fork = :fork AND turn = positions.turn AND samples = :samples
)
ORDER BY positions.turn LIMIT 1
