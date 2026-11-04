CREATE TABLE windows (
    id TEXT PRIMARY KEY, position INTEGER NOT NULL UNIQUE);

CREATE TABLE forks (
    id TEXT PRIMARY KEY, window_id TEXT NOT NULL REFERENCES windows(id), position INTEGER NOT NULL,
    UNIQUE (window_id, position));

CREATE TABLE turns (
    id TEXT PRIMARY KEY, fork_id TEXT NOT NULL REFERENCES forks(id), position INTEGER NOT NULL,
    UNIQUE (fork_id, position));

CREATE TABLE advice (
    id TEXT PRIMARY KEY, turn_id TEXT NOT NULL UNIQUE REFERENCES turns(id), text TEXT NOT NULL,
    score REAL NOT NULL, score_text TEXT, rejected INTEGER NOT NULL);

CREATE TABLE ts (
    id TEXT PRIMARY KEY, advice_id TEXT NOT NULL REFERENCES advice(id), position INTEGER NOT NULL,
    UNIQUE (advice_id, position));

CREATE TABLE files (
    id TEXT PRIMARY KEY, t_id TEXT NOT NULL REFERENCES ts(id), path TEXT NOT NULL,
    content TEXT NOT NULL, UNIQUE (t_id, path));

CREATE TABLE test_results (
    id TEXT PRIMARY KEY, t_id TEXT NOT NULL REFERENCES ts(id), test INTEGER NOT NULL,
    stdout TEXT NOT NULL, stderr TEXT NOT NULL, passed INTEGER NOT NULL, status TEXT NOT NULL,
    UNIQUE (t_id, test));
