WITH attempts AS (
 SELECT value->>'path' AS path,value->>'position' AS id FROM json_each(:directories)
 WHERE value->>'kind'='attempt' AND value->>'parent'=:sample
), outcomes AS (
 SELECT a.*,t.body AS tests,g.body AS generation,
 CASE WHEN coalesce(g.body->>'timed_out',0) OR (g.body->>'error' IS NOT NULL AND g.body->>'error' NOT IN ('',0)) THEN 'failed'
 WHEN t.body->>'all_passed' IS NULL THEN 'unknown' WHEN t.body->>'all_passed' THEN 'passed' ELSE 'failed' END AS outcome
 FROM attempts a LEFT JOIN documents t ON t.path=a.path||'/tests.json'
 LEFT JOIN documents g ON g.path=a.path||'/generation.json'
), files AS (SELECT value->>'path' AS path,value->>'size' AS size FROM json_each(:files)),
rows AS (
 SELECT id,json_object('id',id,'source',a.path,'testsSource',a.path||'/tests.json',
 'tests',json(tests),'generation',json(generation),'outcome',outcome,
 'failure',CASE WHEN generation->>'timed_out' THEN 'Generation timed out before this attempt completed.'||CASE WHEN generation->>'error' IS NOT NULL AND generation->>'error' NOT IN ('',0) THEN char(10)||(generation->>'error') ELSE '' END END,
 'transcriptFiles',json((SELECT json_group_array(json_object('name',path,'source',path,'text',NULL,'bytes',size)) FROM (SELECT * FROM files WHERE path GLOB a.path||'/transcripts/*/*.jsonl' ORDER BY path))),
 'files',json((SELECT json_group_array(json_object('name',substr(path,length(a.path)+6),'source',path,'text',NULL,'bytes',size,'path',CASE WHEN (SELECT count(*) FROM attempts)>1 THEN 'Attempt '||a.id||'/' ELSE '' END||substr(path,length(a.path)+6))) FROM (SELECT * FROM files WHERE path GLOB a.path||'/src/*' ORDER BY path)))) AS payload
 FROM outcomes a
)
SELECT json_group_array(json(payload)) AS payload FROM (SELECT payload FROM rows ORDER BY id);
