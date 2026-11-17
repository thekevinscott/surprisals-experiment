WITH topology AS MATERIALIZED (
 SELECT CAST(value->>'run' AS TEXT) AS run,CAST(value->>'kind' AS TEXT) AS kind,CAST(value->>'window' AS INTEGER) AS window,CAST(value->>'fork' AS INTEGER) AS fork,
 CAST(value->>'turn' AS INTEGER) AS turn,CAST(value->>'sample' AS INTEGER) AS sample,CAST(value->>'attempt' AS INTEGER) AS attempt FROM json_each(:directories)
), info AS MATERIALIZED (SELECT * FROM run_info WHERE :run IS NULL OR run=:run),
-- Materialized dashboard rows need scores and positions, not advice bodies.
turns AS MATERIALIZED (
 SELECT run,source,window,fork,turn,depth,score,metadata->>'advice' AS adviceRef
 FROM evaluated_turns WHERE :run IS NULL OR run=:run
),
latest_attempts AS MATERIALIZED (SELECT run,window,fork,turn,sample,max(attempt) AS attempt FROM topology WHERE kind='attempt' GROUP BY run,window,fork,turn,sample),
sample_results AS MATERIALIZED (
 SELECT s.run,s.window,s.fork,s.turn,count(*) AS count,
 min(coalesce(t.body->>'all_passed',0) AND NOT coalesce(g.body->>'timed_out',0) AND (g.body->>'error' IS NULL OR g.body->>'error' IN ('',0))) AS passed
 FROM topology s
 LEFT JOIN latest_attempts a USING(run,window,fork,turn,sample)
 LEFT JOIN documents t ON t.run=a.run AND t.kind='tests.json' AND t.window=a.window AND t.fork=a.fork AND t.turn=a.turn AND t.sample=a.sample AND t.attempt=a.attempt
 LEFT JOIN documents g ON g.run=a.run AND g.kind='generation.json' AND g.window=a.window AND g.fork=a.fork AND g.turn=a.turn AND g.sample=a.sample AND g.attempt=a.attempt
 WHERE s.kind='sample' GROUP BY s.run,s.window,s.fork,s.turn
), samples AS (
 SELECT e.run,e.window,e.fork,e.turn,coalesce(r.count,0) AS count,coalesce(r.passed,0) AS passed
 FROM turns e LEFT JOIN sample_results r USING(run,window,fork,turn)
), evaluated AS MATERIALIZED (
 SELECT e.*,coalesce(samples.count=(i.settings->>'t_samples') AND (i.settings->>'t_samples')>0 AND samples.passed,0) AS passed
 FROM turns e JOIN samples USING(run,window,fork,turn) JOIN info i USING(run)
), scored AS MATERIALIZED (
 SELECT * FROM evaluated WHERE score IS NOT NULL AND adviceRef GLOB 'advices/*'
 AND substr(adviceRef,9) NOT GLOB '*[^a-f0-9]*'
), last_observed AS (
 SELECT run,max(mtime) AS mtime FROM documents WHERE kind IN ('run.json','metadata.json','tests.json','generation.json') AND (:run IS NULL OR run=:run) GROUP BY run
), windows AS MATERIALIZED (SELECT DISTINCT run,window FROM evaluated),
fork_keys AS (SELECT DISTINCT run,window,fork FROM evaluated),
fork_rows AS MATERIALIZED (
 SELECT run,window,fork,json_object('window',window,'id',fork,
 'turns',coalesce((SELECT max(depth+1) FROM evaluated e WHERE e.run=f.run AND e.window=f.window AND e.fork=f.fork),0),
 'scored',json((SELECT json_group_array(json_array(depth,score,json(CASE WHEN passed THEN 'true' ELSE 'false' END))) FROM (SELECT * FROM scored s WHERE s.run=f.run AND s.window=f.window AND s.fork=f.fork AND depth IS NOT NULL ORDER BY depth,source))),
 'passing',json((SELECT json_group_array(json_array(depth,score)) FROM (SELECT * FROM scored s WHERE s.run=f.run AND s.window=f.window AND s.fork=f.fork AND passed AND depth IS NOT NULL ORDER BY depth,source)))) AS payload
 FROM fork_keys f
), invocations AS (
 SELECT i.run,i.meta,v.value FROM info i,json_each(CASE WHEN json_array_length(i.meta,'$.invocations')>0 THEN i.meta->'$.invocations' ELSE json_array(json(i.meta)) END) v
), runtimes AS (
 SELECT run,CASE WHEN count(seconds)=count(*) THEN sum(seconds) END AS elapsed FROM (
  SELECT run,max(0,
   CASE WHEN value->>'ended_by'='lost'
    THEN (SELECT mtime FROM stderr_files f WHERE f.run=v.run AND f.file=value->>'stderr')/1000.0
    ELSE coalesce(unixepoch(value->>'ended','subsec'),:now/1000.0) END
   -unixepoch(coalesce(value->>'started',meta->>'created'),'subsec')) AS seconds FROM invocations v
 ) GROUP BY run
/* Costs disabled for now.
), costs AS (
 SELECT *,max(0,(coalesce(unixepoch(ended,'subsec'),:now/1000.0)-unixepoch(awsLaunched,'subsec')))/3600*0.1008 AS awsCost
 FROM cost_rows WHERE :run IS NULL OR id=:run
*/
), rows AS (
 SELECT r.strategy,r.problem,r.id,json_object('id',r.id,'problem',r.problem,'strategy',r.strategy,
 'exit',current->>'exit_code',
 'status',CASE WHEN current->>'ended' IS NULL THEN 'Open' WHEN current->>'exit_code'=0 THEN 'Complete' ELSE 'Stopped / failed' END,
 'outcome',CASE WHEN current->>'ended' IS NULL AND current->>'exit_code' IS NULL THEN 'open' WHEN current->>'exit_code'=0 THEN 'passed' ELSE 'failed' END,
 'cause',coalesce(current->>'error',CASE WHEN current->>'exit_code'!=0 OR current->>'exit_code' IS NULL THEN current->>'ended_by' END),
 'started',coalesce(current->>'started',meta->>'created'),'ended',current->>'ended',
 'observed',strftime('%Y-%m-%dT%H:%M:%fZ',o.mtime/1000,'unixepoch'),
 'elapsed',rt.elapsed,'duration',rt.elapsed,'runtimeAsOf',:now,
 'turns',coalesce((SELECT max(depth+1) FROM evaluated e WHERE e.run=i.run),0),'windows',(SELECT count(*) FROM windows w WHERE w.run=i.run),
 'best',(SELECT min(score) FROM scored s WHERE s.run=i.run AND passed),
 'bestTarget',(SELECT source FROM scored s WHERE s.run=i.run AND passed ORDER BY score,source LIMIT 1),
 'samples',settings->>'t_samples','forkTurns',settings->>'fork_turns','soloTurns',settings->>'window_solo_turns',
 'windowPositions',json((SELECT json_group_array(json_object('id',window,'depth',CASE WHEN window=0 THEN 0 ELSE window*((settings->>'fork_turns')+(settings->>'window_solo_turns')) END)) FROM (SELECT window FROM windows w WHERE w.run=i.run AND (window=0 OR (settings->>'fork_turns')+(settings->>'window_solo_turns') IS NOT NULL) ORDER BY window))),
 'scored',json((SELECT json_group_array(json_array(depth,score,json(CASE WHEN passed THEN 'true' ELSE 'false' END))) FROM (SELECT * FROM scored s WHERE s.run=i.run AND depth IS NOT NULL ORDER BY depth,source))),
 'passing',json((SELECT json_group_array(json_array(depth,score)) FROM (SELECT * FROM scored s WHERE s.run=i.run AND passed AND depth IS NOT NULL ORDER BY depth,score,source))),
 'forks',json((SELECT json_group_array(json(payload)) FROM (SELECT payload FROM fork_rows f WHERE f.run=i.run ORDER BY window,fork)))
 /*, 'uCost',c.uCost,'tCost',c.tCost,'modelCost',c.uCost+c.tCost,'awsLaunched',c.awsLaunched,'awsCost',c.awsCost */
 ) AS payload
 FROM info i JOIN run_identity r ON r.id=i.run
 LEFT JOIN last_observed o ON o.run=i.run LEFT JOIN runtimes rt ON rt.run=i.run /* LEFT JOIN costs c ON c.id=i.run */
)
SELECT json_group_array(json(payload)) AS payload FROM (SELECT payload FROM rows ORDER BY strategy,problem,id);
