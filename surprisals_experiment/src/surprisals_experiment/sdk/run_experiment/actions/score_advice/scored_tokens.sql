SELECT metadata.content -> 'tokens' AS tokens
FROM './windows/*/forks/*/turns/*/advice.txt' AS advice
JOIN './windows/*/forks/*/turns/*/metadata.json' AS metadata ON metadata.dir = advice.dir
WHERE advice.content = {advice} AND metadata.content -> 'tokens' IS NOT NULL
LIMIT 1
