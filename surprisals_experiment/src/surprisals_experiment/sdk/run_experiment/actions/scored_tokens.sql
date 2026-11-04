SELECT m.path FROM './attempts/*/advices/*/advice.txt' AS a
JOIN './attempts/*/advices/*/metadata.json' AS m ON m.dir = a.dir
WHERE a.content = '{advice}' AND m.content ->> 'tokens' IS NOT NULL LIMIT 1
