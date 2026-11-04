SELECT input.value AS input, output.value AS output
FROM './input_output.json' AS suite,
  json_each(suite.content, '$.inputs') AS input
  JOIN json_each(suite.content, '$.outputs') AS output ON output.key = input.key
ORDER BY input.key
