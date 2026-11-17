WITH topology AS MATERIALIZED (
 SELECT value->>'path' AS path,value->>'kind' AS kind,value->>'position' AS position,value->>'window' AS window,
 value->>'fork' AS fork,value->>'turn' AS turn,value->>'sample' AS sample,value->>'attempt' AS attempt FROM json_each(:directories)
), attempts AS (
 SELECT a.*,t.body AS tests,g.body AS generation,
 row_number() OVER (PARTITION BY a.window,a.fork,a.turn,a.sample ORDER BY a.attempt DESC) AS rank
 FROM topology a
 LEFT JOIN documents t ON t.run=:run AND t.kind='tests.json' AND t.window=a.window AND t.fork=a.fork AND t.turn=a.turn AND t.sample=a.sample AND t.attempt=a.attempt
 LEFT JOIN documents g ON g.run=:run AND g.kind='generation.json' AND g.window=a.window AND g.fork=a.fork AND g.turn=a.turn AND g.sample=a.sample AND g.attempt=a.attempt
 WHERE a.kind='attempt'
), samples AS MATERIALIZED (
 SELECT s.*,json_object('id',s.position,'source',s.path,'latest',json(CASE WHEN a.path IS NULL THEN NULL ELSE
 json_object('id',a.position,
 'outcome',CASE WHEN coalesce(generation->>'timed_out',0) OR (generation->>'error' IS NOT NULL AND generation->>'error' NOT IN ('',0)) THEN 'failed' WHEN tests->>'all_passed' IS NULL THEN 'unknown' WHEN tests->>'all_passed' THEN 'passed' ELSE 'failed' END,
 'tests',json(CASE WHEN tests IS NULL THEN NULL ELSE json_object('all_passed',json(tests->'all_passed'),'passed',tests->>'passed','total',tests->>'total') END),
 'generation',json(CASE WHEN generation IS NULL THEN NULL ELSE json_object('timed_out',json(generation->'timed_out'),'error',generation->>'error','exit_code',generation->>'exit_code') END)) END)) AS payload
 FROM topology s LEFT JOIN attempts a ON a.rank=1 AND a.window=s.window AND a.fork=s.fork AND a.turn=s.turn AND a.sample=s.sample WHERE s.kind='sample'
), turns_data AS MATERIALIZED (
 SELECT t.*,json_object('id',t.position,'source',t.path,
 'transcriptPath','windows/'||t.window||'/forks/'||t.fork||'/u/transcript.jsonl',
 'error',d.body->>'error','metadata',json(d.body),
 'advice',txt.body,'adviceSource',CASE WHEN json_type(d.body,'$.advice')='text' THEN (d.body->>'advice')||'/advice.txt' END,
 'measurement',a.body->>'score','tokens',json(a.body->'tokens'),'adviceMetadata',json(a.body),
 'unit',CASE :strategy WHEN 'surprisal' THEN 'bits' WHEN 'characters' THEN 'chars' ELSE 'score' END,
 'solo',json(CASE WHEN :forkTurns IS NOT NULL AND t.position>=:forkTurns THEN 'true' ELSE 'false' END),
 'sampleColumns',max(coalesce(:samples,0),(SELECT count(*) FROM samples s WHERE s.window=t.window AND s.fork=t.fork AND s.turn=t.turn)),
 'samples',json((SELECT json_group_array(json(payload)) FROM (SELECT payload FROM samples s WHERE s.window=t.window AND s.fork=t.fork AND s.turn=t.turn ORDER BY position)))
 ) AS payload
 FROM topology t
 LEFT JOIN documents d ON d.run=:run AND d.kind='metadata.json' AND d.window=t.window AND d.fork=t.fork AND d.turn=t.turn
 LEFT JOIN documents a ON a.run=:run AND a.kind='advice.json' AND d.body->>'advice' GLOB 'advices/*' AND a.advice=substr(d.body->>'advice',9)
 LEFT JOIN advice_text txt ON txt.run=:run AND d.body->>'advice' GLOB 'advices/*' AND txt.advice=substr(d.body->>'advice',9)
 WHERE t.kind='turn'
), advice_order AS (
 SELECT window,fork,turn,lag(json_object('advice',payload->>'advice','tokens',json(payload->'tokens'))) OVER (PARTITION BY window,fork ORDER BY position) AS previous FROM turns_data WHERE payload->>'advice' IS NOT NULL
), advice_navigation AS MATERIALIZED (
 SELECT t.*,json_set(t.payload,'$.previousAdvice',json(a.previous)) AS navigation FROM turns_data t JOIN advice_order a USING(window,fork,turn)
), fork_rows AS MATERIALIZED (
 SELECT f.*,json_object('id',f.position,'source',f.path,'transcriptPath',f.path||'/u/transcript.jsonl',
 'parallel',json((SELECT json_group_array(json(payload)) FROM (SELECT payload FROM turns_data t WHERE t.window=f.window AND t.fork=f.fork AND (:forkTurns IS NULL OR t.position<:forkTurns) ORDER BY position))),
 'solo',json((SELECT json_group_array(json(payload)) FROM (SELECT payload FROM turns_data t WHERE t.window=f.window AND t.fork=f.fork AND :forkTurns IS NOT NULL AND t.position>=:forkTurns ORDER BY position))),
 'navigation',json((SELECT json_group_array(json(payload)) FROM (SELECT json_remove(payload,'$.samples','$.adviceMetadata') AS payload FROM turns_data t WHERE t.window=f.window AND t.fork=f.fork ORDER BY position))),
 'adviceNavigation',json((SELECT json_group_array(json(payload)) FROM (SELECT navigation AS payload FROM advice_navigation t WHERE t.window=f.window AND t.fork=f.fork ORDER BY position)))
 ) AS payload FROM topology f WHERE f.kind='fork'
), window_rows AS (
 SELECT w.position,json_object('id',w.position,
 'forks',json((SELECT json_group_array(json(payload)) FROM (SELECT payload FROM fork_rows f WHERE f.window=w.window ORDER BY position))),
 'turnIds',json((SELECT json_group_array(position) FROM (SELECT DISTINCT position FROM turns_data t WHERE t.window=w.position AND (:forkTurns IS NULL OR t.position<:forkTurns) ORDER BY position))),
 'sampleColumns',coalesce(:samples,(SELECT max(json_array_length(payload,'$.samples')) FROM turns_data t WHERE t.window=w.position),1),
 'continuedForks',json((SELECT json_group_array(position) FROM (SELECT position FROM fork_rows f WHERE f.window=w.window AND json_array_length(payload,'$.solo')>0 ORDER BY position)))) AS payload
 FROM topology w WHERE w.kind='window'
)
SELECT json_group_array(json(payload)) AS payload FROM (SELECT payload FROM window_rows ORDER BY position);
