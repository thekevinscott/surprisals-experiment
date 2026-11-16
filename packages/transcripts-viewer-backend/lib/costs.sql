CREATE TABLE cost_runs (id TEXT PRIMARY KEY, meta TEXT NOT NULL);
CREATE TABLE usage_records (run TEXT, kind TEXT, path TEXT, line INTEGER, completion_id TEXT, cost REAL, incomplete INTEGER, billable INTEGER);
CREATE TABLE launches (run TEXT, path TEXT, launched TEXT);
CREATE TABLE pods (id TEXT, gpu TEXT, costPerHr REAL, start TEXT, stop TEXT);
CREATE VIEW usage_ranked AS
SELECT *, row_number() OVER (PARTITION BY run,kind,
  CASE WHEN completion_id IS NOT NULL AND completion_id != '' THEN completion_id ELSE path || ':' || line END,
  CASE WHEN completion_id IS NOT NULL AND completion_id != '' THEN 1 ELSE 0 END
  ORDER BY path,line) AS occurrence FROM usage_records WHERE billable;
CREATE VIEW model_costs AS
SELECT run,kind,CASE WHEN count(cost)=count(*) THEN sum(cost) END AS cost
FROM usage_ranked WHERE occurrence=1 GROUP BY run,kind;
CREATE VIEW cost_rows AS
WITH invocation AS (
  SELECT id,coalesce(meta->'$.invocations[#-1]',meta) AS current FROM cost_runs
)
SELECT id,
 (SELECT cost FROM model_costs WHERE run=id AND kind='u') AS uCost,
 (SELECT cost FROM model_costs WHERE run=id AND kind='t') AS tCost,
 (SELECT min(launched) FROM launches WHERE run=id) AS awsLaunched,
 current->>'ended' AS ended
FROM invocation;
