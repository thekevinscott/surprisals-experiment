SELECT
  json_type(content, '$.fn_name') IS NOT NULL AS fn_name,
  (SELECT count(*) FROM json_each(content, '$.inputs')) AS cases,
  (SELECT count(*) FROM json_each(content, '$.inputs') WHERE type != 'text')
    + (SELECT count(*) FROM json_each(content, '$.outputs') WHERE type != 'text') AS non_strings
FROM './input_output.json'
