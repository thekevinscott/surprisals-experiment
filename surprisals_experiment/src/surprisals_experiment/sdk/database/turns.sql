CREATE TABLE turns (
    id TEXT PRIMARY KEY, fork_id TEXT NOT NULL REFERENCES forks(id), position INTEGER NOT NULL,
    UNIQUE (fork_id, position))
