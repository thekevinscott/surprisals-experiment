CREATE TABLE forks (
    id TEXT PRIMARY KEY, window_id TEXT NOT NULL REFERENCES windows(id), position INTEGER NOT NULL,
    UNIQUE (window_id, position))
