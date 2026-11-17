CREATE TABLE pod_records (path TEXT PRIMARY KEY, id TEXT, gpu TEXT, costPerHr REAL, start TEXT, stop TEXT);

CREATE TABLE stderr_files (path TEXT PRIMARY KEY, run TEXT, file TEXT, launched TEXT, mtime REAL);
CREATE INDEX stderr_files_run ON stderr_files(run,file);

CREATE TABLE identities (path TEXT PRIMARY KEY, run TEXT, kind TEXT, problem TEXT, body TEXT, error TEXT);

CREATE TABLE documents (path TEXT PRIMARY KEY, run TEXT, kind TEXT, window INTEGER, fork INTEGER, turn INTEGER, sample INTEGER, attempt INTEGER, advice TEXT, body TEXT, error TEXT, mtime REAL);
CREATE INDEX documents_position ON documents(run,kind,window,fork,turn,sample,attempt);
CREATE INDEX documents_advice ON documents(run,advice);

CREATE TABLE advice_text (path TEXT PRIMARY KEY, run TEXT, advice TEXT, body TEXT);
CREATE INDEX advice_text_advice ON advice_text(run,advice);

CREATE TABLE transcript_lines (run TEXT, path TEXT, kind TEXT, line INTEGER, offset INTEGER, length INTEGER, type TEXT, completion_id TEXT, cost REAL, incomplete INTEGER, billable INTEGER);
CREATE INDEX transcript_lines_path ON transcript_lines(run,path,line);

CREATE VIEW run_identity AS
SELECT r.run AS id,coalesce(r.problem,s.problem,'Unknown') AS problem,
 coalesce(r.body->>'$.params."cap-strategy"',s.body->>'cap_strategy','Unknown') AS strategy
FROM identities r LEFT JOIN identities s ON s.run=r.run AND s.kind='settings.json' WHERE r.kind='run.json';

CREATE VIEW run_info AS
SELECT r.run,r.body AS meta,coalesce(s.body,'{}') AS settings,coalesce(r.body->'$.invocations[#-1]',r.body) AS current,r.mtime
FROM documents r LEFT JOIN documents s ON s.run=r.run AND s.kind='settings.json' WHERE r.kind='run.json';

CREATE VIEW evaluated_turns AS
SELECT d.run,'windows/'||d.window||'/forks/'||d.fork||'/turns/'||d.turn AS source,d.window,d.fork,d.turn,d.body AS metadata,d.mtime,
 a.body AS adviceMetadata,t.body AS advice,
 CASE WHEN d.window=0 THEN d.turn ELSE d.window*((i.settings->>'fork_turns')+(i.settings->>'window_solo_turns'))+d.turn END AS depth,
 CASE WHEN json_type(a.body,'$.score') IN ('integer','real') THEN a.body->>'score' END AS score
FROM documents d LEFT JOIN run_info i ON i.run=d.run
LEFT JOIN documents a ON a.run=d.run AND a.kind='advice.json' AND d.body->>'advice' GLOB 'advices/*' AND a.advice=substr(d.body->>'advice',9)
LEFT JOIN advice_text t ON t.run=d.run AND d.body->>'advice' GLOB 'advices/*' AND t.advice=substr(d.body->>'advice',9)
WHERE d.kind='metadata.json';

CREATE VIEW usage_ranked AS
SELECT *,row_number() OVER (PARTITION BY run,kind,
  CASE WHEN completion_id IS NOT NULL AND completion_id != '' THEN completion_id ELSE path || ':' || line END,
  CASE WHEN completion_id IS NOT NULL AND completion_id != '' THEN 1 ELSE 0 END
  ORDER BY path,line) AS occurrence FROM transcript_lines WHERE billable;

CREATE VIEW model_costs AS
SELECT run,kind,CASE WHEN count(cost)=count(*) THEN sum(cost) END AS cost
FROM usage_ranked WHERE occurrence=1 GROUP BY run,kind;

CREATE VIEW cost_rows AS
WITH models AS MATERIALIZED (SELECT * FROM model_costs),
 launch_times AS (SELECT run,min(launched) AS launched FROM stderr_files GROUP BY run)
SELECT i.run AS id,u.cost AS uCost,t.cost AS tCost,l.launched AS awsLaunched,i.current->>'ended' AS ended
FROM run_info i
LEFT JOIN models u ON u.run=i.run AND u.kind='u'
LEFT JOIN models t ON t.run=i.run AND t.kind='t'
LEFT JOIN launch_times l ON l.run=i.run;
