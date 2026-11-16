WITH invocations AS (
 SELECT value FROM json_each(CASE WHEN json_array_length(:meta,'$.invocations')>0
 THEN json_extract(:meta,'$.invocations') ELSE json_array(json(:meta)) END)
), durations AS (
 SELECT max(0,
   CASE WHEN value->>'ended_by'='lost'
     THEN (SELECT json_extract(:stderr,'$."'||(value->>'stderr')||'"'))/1000.0
     ELSE coalesce(unixepoch(value->>'ended','subsec'),:now/1000.0) END
   -unixepoch(coalesce(value->>'started',json_extract(:meta,'$.created')),'subsec')
 ) AS seconds FROM invocations
)
SELECT CASE WHEN count(seconds)=count(*) THEN sum(seconds) END AS elapsed,
 :now AS runtimeAsOf FROM durations;
