SELECT content ->> 'passed' AS passed, content ->> 'total' AS total, content ->> 'all_passed' AS all_passed
FROM './windows/*/forks/*/turns/*/ts/*/tests.json'
WHERE dir LIKE {turn} || '/ts/%'
ORDER BY length(dir), dir
