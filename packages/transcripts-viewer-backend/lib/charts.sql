WITH input AS (SELECT json(:row) AS row),
forks AS (
 SELECT value AS fork, value->>'window' AS window,value->>'id' AS id,
 CASE WHEN value->>'window'=0 THEN 0 ELSE (value->>'window')*((row->>'forkTurns')+(row->>'soloTurns')) END AS start,
 row->>'forkTurns' AS parallel,row->>'soloTurns' AS solo,
 row_number() OVER (ORDER BY value->>'window',value->>'id')-1 AS colorIndex
 FROM input,json_each(row,'$.forks')
), scopes AS (
 SELECT 'run' AS key,NULL AS window,NULL AS fork,NULL AS start,NULL AS end
 UNION ALL SELECT window||'/'||id||'/parallel',window,id,start,start+parallel FROM forks
 UNION ALL SELECT window||'/'||id||'/solo',window,id,start+parallel,start+parallel+solo FROM forks
), points AS (
 SELECT f.window,f.id,p.value AS point,p.value->>0 AS depth,p.value->>1 AS score,p.value->>2 AS passed FROM forks f,json_each(f.fork,'$.scored') p
), passing AS (
 SELECT f.window,f.id,p.value->>0 AS depth,p.value->>1 AS score FROM forks f,json_each(f.fork,'$.passing') p
), scoped_passing AS (
 SELECT s.key,p.*,min(score) OVER (PARTITION BY s.key,p.window,p.id ORDER BY depth,score ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS previous
 FROM scopes s JOIN passing p ON s.key='run' OR (p.window=s.window AND p.id=s.fork AND p.depth>=s.start AND p.depth<s.end)
), series AS (
 SELECT s.key,f.window,f.id,json_object(
 'strategy',row->>'strategy','problem',row->>'problem','cell',(row->>'id')||'/windows/'||f.window||'/forks/'||f.id,
 'colorIndex',f.colorIndex,'running',json(CASE WHEN row->>'ended' IS NULL THEN 'true' ELSE 'false' END),'exit_code',row->>'exit',
 'window',f.window,'fork',f.id,'turnStart',f.start,
 'continues',json(CASE WHEN (f.fork->>'turns')>f.start+f.parallel THEN 'true' ELSE 'false' END),
 'label','Window '||f.window||' · Fork '||f.id,
 'scored',json((SELECT json_group_array(json(point)) FROM (SELECT point FROM points p WHERE p.window=f.window AND p.id=f.id AND (s.key='run' OR (depth>=s.start AND depth<s.end)) ORDER BY depth))),
 'passing',json((SELECT json_group_array(json_array(depth,score)) FROM (SELECT depth,score FROM scoped_passing p WHERE p.key=s.key AND p.window=f.window AND p.id=f.id ORDER BY depth,score))),
 'advice',json((SELECT json_group_array(json_array(depth,score)) FROM (SELECT depth,score FROM scoped_passing p WHERE p.key=s.key AND p.window=f.window AND p.id=f.id AND (previous IS NULL OR score<previous) ORDER BY depth,score))),
 'targets',json((SELECT json_group_object(depth,json_object('window',f.window,'fork',f.id,'turn',depth-f.start)) FROM points p WHERE p.window=f.window AND p.id=f.id))
 ) AS payload
 FROM scopes s JOIN forks f ON s.key='run' OR (s.window=f.window AND s.fork=f.id) CROSS JOIN input
), charts AS (
 SELECT s.key,json_object('arms',json_array(row->>'strategy'),
 'series',json((SELECT json_group_array(json(payload)) FROM series WHERE key=s.key)),
 'windowPositions',json(coalesce(row->'windowPositions','[]')),
 'domains',json_object(
 'advice',json_object('x',json_array(coalesce(s.start,0),coalesce(s.end,max(10,coalesce(row->>'turns',0))+2)),'y',json_array(0,CASE WHEN row->>'strategy'='surprisal' THEN 1.05 ELSE max(1,coalesce((SELECT max(score) FROM points),1))*1.05 END)),
 'surprisal',json_object('x',json_array(coalesce(s.start,0),coalesce(s.end,max(10,coalesce(row->>'turns',0))+2)),'y',json_array(0,CASE WHEN row->>'strategy'='surprisal' THEN max(1,coalesce((SELECT max(score) FROM points),1))*1.05 ELSE 1.05 END))
 )) AS payload FROM scopes s CROSS JOIN input
)
SELECT json_group_object(key,json(payload)) AS payload FROM charts;
