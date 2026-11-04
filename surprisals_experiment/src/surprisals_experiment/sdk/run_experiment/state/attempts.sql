SELECT attempt,
  max(CASE WHEN kind = 'advice.txt' THEN content END) AS advice,
  max(CASE WHEN kind = 'metadata.json' THEN json_extract(content, '$.measurement') END) AS measurement,
  max(kind = 'feedback.txt') AS feedback,
  sum(kind = 'tests.json') = {samples} AS tested,
  sum(CASE WHEN kind = 'tests.json' THEN json_extract(content, '$.all_passed') ELSE 0 END) = {samples} AS passed
FROM artifacts WHERE attempt IS NOT NULL GROUP BY attempt
