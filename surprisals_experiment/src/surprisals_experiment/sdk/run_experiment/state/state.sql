WITH latest AS (
  SELECT max(position) AS position FROM windows
), best AS (
  SELECT min(score) AS current,
         min(CASE WHEN window < latest.position THEN score END) AS previous
  FROM evaluated_turns CROSS JOIN latest
  WHERE passed = 1 AND samples = :samples AND score IS NOT NULL
    AND window <= latest.position
)
SELECT latest.position, best.current, best.previous,
       CASE WHEN latest.position = 0 THEN 0
            WHEN best.previous IS NULL THEN best.current IS NULL
            WHEN best.previous = 0 THEN 1
            ELSE (best.previous - best.current) / (1.0 * best.previous) < :improvement
       END AS stop
FROM latest CROSS JOIN best
