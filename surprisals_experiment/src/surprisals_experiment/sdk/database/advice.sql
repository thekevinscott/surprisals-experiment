CREATE TABLE advice (
    id TEXT PRIMARY KEY, turn_id TEXT NOT NULL UNIQUE REFERENCES turns(id), text TEXT NOT NULL,
    score REAL NOT NULL, score_text TEXT, rejected INTEGER NOT NULL)
