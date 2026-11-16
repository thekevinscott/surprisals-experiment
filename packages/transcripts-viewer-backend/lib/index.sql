WITH runs AS (
 SELECT r.id,coalesce(r.problem,s.problem,'Unknown') AS problem,
 coalesce(r.body->>'$.params."cap-strategy"',s.body->>'cap_strategy','Unknown') AS strategy
 FROM identities r LEFT JOIN identities s ON s.id=r.id AND s.kind='settings.json' WHERE r.kind='run.json'
), strategies AS (SELECT strategy,count(*) AS count FROM runs GROUP BY strategy),
problems AS (SELECT strategy,problem,count(*) AS count FROM runs GROUP BY strategy,problem)
SELECT json_object('rows',json((SELECT json_group_array(json_object('id',id,'problem',problem,'strategy',strategy,
 'relatedRuns',json((SELECT json_group_array(json_object('id',id,'problem',problem,'strategy',strategy)) FROM (SELECT * FROM runs x WHERE x.strategy=r.strategy AND x.problem=r.problem ORDER BY id))),
 'problemOptions',json((SELECT json_group_array(json_object('value',problem,'description',count||' runs · '||strategy)) FROM problems p WHERE p.strategy=r.strategy)))) FROM (SELECT * FROM runs ORDER BY id) r)),
 'strategyOptions',json((SELECT json_group_array(json_object('value',strategy,'description',count||' runs')) FROM strategies))) AS payload;
