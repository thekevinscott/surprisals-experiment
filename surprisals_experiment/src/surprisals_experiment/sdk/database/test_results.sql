CREATE TABLE test_results (
    id TEXT PRIMARY KEY, t_id TEXT NOT NULL REFERENCES ts(id), test INTEGER NOT NULL,
    stdout TEXT NOT NULL, stderr TEXT NOT NULL, passed INTEGER NOT NULL, status TEXT NOT NULL,
    UNIQUE (t_id, test))
