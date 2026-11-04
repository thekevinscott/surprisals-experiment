-- The caller checks this only after window :window is complete.
WITH bests AS (
  SELECT min(CASE WHEN window < :window THEN score END) AS previous,
         min(score) AS current
  FROM complete_turns
  WHERE window <= :window AND samples = :samples AND passed = 1
)
SELECT :window > 0 AND (
  current IS NULL OR previous = 0
  OR (previous IS NOT NULL AND current > previous * 0.95)
) AS stopped
FROM bests
