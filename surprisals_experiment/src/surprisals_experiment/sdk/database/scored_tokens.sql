SELECT metadata.content -> 'tokens' AS tokens
FROM './windows/0/forks/0/turns/*/advice.txt' AS advice
JOIN './windows/0/forks/0/turns/*/metadata.json' AS metadata ON metadata.dir = advice.dir
WHERE advice.content = {advice} AND metadata.content -> 'tokens' IS NOT NULL
LIMIT 1
