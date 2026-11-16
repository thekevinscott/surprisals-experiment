CREATE TABLE pod_records (path TEXT PRIMARY KEY, id TEXT, gpu TEXT, costPerHr REAL, start TEXT, stop TEXT);
CREATE TABLE launch_events (path TEXT, launched TEXT);
CREATE TABLE identities (id TEXT, path TEXT PRIMARY KEY, kind TEXT, problem TEXT, body TEXT);
CREATE TABLE documents (
 path TEXT PRIMARY KEY, parent TEXT, kind TEXT, window INTEGER, fork INTEGER,
 turn INTEGER, sample INTEGER, attempt INTEGER, body TEXT, mtime REAL
);
CREATE TABLE advice_text (path TEXT PRIMARY KEY, body TEXT);
CREATE VIEW turns AS
SELECT parent AS id, 'windows/'||window||'/forks/'||fork AS fork_id,turn AS position
FROM documents WHERE kind='metadata.json';
CREATE VIEW run_info AS
SELECT r.body AS meta,coalesce(s.body,'{}') AS settings,
 coalesce(r.body->'$.invocations[#-1]',r.body) AS current,r.mtime
FROM documents r LEFT JOIN documents s ON s.path='settings.json' WHERE r.path='run.json';
CREATE VIEW evaluated_turns AS
SELECT d.parent AS source,d.window,d.fork,d.turn,d.body AS metadata,d.mtime,
 a.body AS adviceMetadata,t.body AS advice,
 CASE WHEN d.window=0 THEN d.turn ELSE d.window*((SELECT settings->>'fork_turns' FROM run_info)+(SELECT settings->>'window_solo_turns' FROM run_info))+d.turn END AS depth,
 CASE WHEN json_type(a.body,'$.score') IN ('integer','real') THEN a.body->>'score' END AS score
FROM documents d
LEFT JOIN documents a ON a.path=(d.body->>'advice')||'/advice.json'
LEFT JOIN advice_text t ON t.path=(d.body->>'advice')||'/advice.txt'
WHERE d.kind='metadata.json';
