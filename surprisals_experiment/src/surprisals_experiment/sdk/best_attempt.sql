WITH attempts AS ({attempts})
SELECT attempt, measurement FROM attempts
WHERE tested AND passed AND measurement IS NOT NULL
ORDER BY measurement, attempt LIMIT 1
