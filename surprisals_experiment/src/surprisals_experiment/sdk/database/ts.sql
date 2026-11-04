CREATE TABLE ts (
    id TEXT PRIMARY KEY, advice_id TEXT NOT NULL REFERENCES advice(id), position INTEGER NOT NULL,
    UNIQUE (advice_id, position))
