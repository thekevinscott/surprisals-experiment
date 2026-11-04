CREATE TABLE files (
    id TEXT PRIMARY KEY, t_id TEXT NOT NULL REFERENCES ts(id), path TEXT NOT NULL,
    content TEXT NOT NULL, UNIQUE (t_id, path))
