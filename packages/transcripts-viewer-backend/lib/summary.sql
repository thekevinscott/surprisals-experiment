WITH topology AS (SELECT value->>'path' AS path,value->>'kind' AS kind,value->>'parent' AS parent,value->>'position' AS position FROM json_each(:directories)),
latest_attempts AS (SELECT *,row_number() OVER (PARTITION BY parent ORDER BY position DESC) AS rank FROM topology WHERE kind='attempt'),
samples AS (
 SELECT e.source,count(s.path) AS count,
 coalesce(min(coalesce(t.body->>'all_passed',0) AND NOT coalesce(g.body->>'timed_out',0) AND (g.body->>'error' IS NULL OR g.body->>'error' IN ('',0))),0) AS passed
 FROM evaluated_turns e
 LEFT JOIN topology s ON s.parent=e.source AND s.kind='sample'
 LEFT JOIN latest_attempts a ON a.parent=s.path AND a.rank=1
 LEFT JOIN documents t ON t.path=a.path||'/tests.json'
 LEFT JOIN documents g ON g.path=a.path||'/generation.json'
 GROUP BY e.source
), evaluated AS (
 SELECT e.*,coalesce(samples.count=(SELECT settings->>'t_samples' FROM run_info)
 AND (SELECT settings->>'t_samples' FROM run_info)>0 AND samples.passed,0) AS passed
 FROM evaluated_turns e JOIN samples USING(source)
), scored AS (
 SELECT * FROM evaluated WHERE score IS NOT NULL AND metadata->>'advice' GLOB 'advices/*'
 AND substr(metadata->>'advice',9) NOT GLOB '*[^a-f0-9]*'
), last_observed AS (
 SELECT max(mtime) AS mtime FROM documents WHERE kind IN ('run.json','metadata.json','tests.json','generation.json')
), windows AS (SELECT DISTINCT window FROM evaluated ORDER BY window),
fork_keys AS (SELECT DISTINCT window,fork FROM evaluated ORDER BY window,fork),
fork_rows AS (
 SELECT window,fork,json_object('window',window,'id',fork,
 'turns',coalesce((SELECT max(depth+1) FROM evaluated e WHERE e.window=f.window AND e.fork=f.fork),0),
 'scored',json((SELECT json_group_array(json_array(depth,score,json(CASE WHEN passed THEN 'true' ELSE 'false' END))) FROM (SELECT * FROM scored s WHERE s.window=f.window AND s.fork=f.fork AND depth IS NOT NULL ORDER BY depth,source))),
 'passing',json((SELECT json_group_array(json_array(depth,score)) FROM (SELECT * FROM scored s WHERE s.window=f.window AND s.fork=f.fork AND passed AND depth IS NOT NULL ORDER BY depth,source)))) AS payload
 FROM fork_keys f
)
SELECT json_object('id',:id,'problem',:problem,'strategy',:strategy,
 'exit',current->>'exit_code',
 'status',CASE WHEN current->>'ended' IS NULL THEN 'Open' WHEN current->>'exit_code'=0 THEN 'Complete' ELSE 'Stopped / failed' END,
 'outcome',CASE WHEN current->>'ended' IS NULL AND current->>'exit_code' IS NULL THEN 'open' WHEN current->>'exit_code'=0 THEN 'passed' ELSE 'failed' END,
 'cause',coalesce(current->>'error',CASE WHEN current->>'exit_code'!=0 OR current->>'exit_code' IS NULL THEN current->>'ended_by' END),
 'started',coalesce(current->>'started',meta->>'created'),'ended',current->>'ended',
 'observed',strftime('%Y-%m-%dT%H:%M:%fZ',(SELECT mtime FROM last_observed)/1000,'unixepoch'),
 'elapsed',max(0,coalesce(unixepoch(current->>'ended','subsec'),(SELECT mtime FROM last_observed)/1000)-unixepoch(coalesce(current->>'started',meta->>'created'),'subsec')),
 'duration',max(0,coalesce(unixepoch(current->>'ended','subsec'),:now/1000.0)-unixepoch(coalesce(current->>'started',meta->>'created'),'subsec')),
 'turns',coalesce((SELECT max(depth+1) FROM evaluated),0),'windows',(SELECT count(*) FROM windows),
 'best',(SELECT min(score) FROM scored WHERE passed),
 'bestTarget',(SELECT source FROM scored WHERE passed ORDER BY score,source LIMIT 1),
 'samples',settings->>'t_samples','forkTurns',settings->>'fork_turns','soloTurns',settings->>'window_solo_turns',
 'windowPositions',json((SELECT json_group_array(json_object('id',window,'depth',CASE WHEN window=0 THEN 0 ELSE window*((settings->>'fork_turns')+(settings->>'window_solo_turns')) END)) FROM windows WHERE window=0 OR (settings->>'fork_turns')+(settings->>'window_solo_turns') IS NOT NULL)),
 'scored',json((SELECT json_group_array(json_array(depth,score,json(CASE WHEN passed THEN 'true' ELSE 'false' END))) FROM (SELECT * FROM scored WHERE depth IS NOT NULL ORDER BY depth,source))),
 'passing',json((SELECT json_group_array(json_array(depth,score)) FROM (SELECT * FROM scored WHERE passed AND depth IS NOT NULL ORDER BY depth,score,source))),
 'forks',json((SELECT json_group_array(json(payload)) FROM fork_rows))
) AS payload FROM run_info;
