CREATE TABLE windows (
  id       TEXT PRIMARY KEY,            -- 'windows/W'
  position INTEGER NOT NULL UNIQUE      -- W, for ordering
);

CREATE TABLE forks (
  id        TEXT PRIMARY KEY,           -- 'windows/W/forks/F'
  window_id TEXT NOT NULL REFERENCES windows(id),
  position  INTEGER NOT NULL,           -- F
  UNIQUE (window_id, position)
);

CREATE TABLE turns (
  id       TEXT PRIMARY KEY,            -- 'windows/W/forks/F/turns/N'
  fork_id  TEXT NOT NULL REFERENCES forks(id),
  position INTEGER NOT NULL,            -- N
  UNIQUE (fork_id, position)
);

CREATE TABLE advices (
  id         TEXT PRIMARY KEY,          -- 'advices/<sha256>'
  text       TEXT NOT NULL UNIQUE,
  score      NUMERIC,                   -- NULL until scored (chars or total bits)
  score_text TEXT                       -- per-token bits rendering, NULL in chars mode
);

CREATE TABLE turn_advice (
  turn_id   TEXT NOT NULL UNIQUE REFERENCES turns(id),
  advice_id TEXT NOT NULL REFERENCES advices(id)
);

CREATE TABLE ts (
  id        TEXT PRIMARY KEY,           -- 'windows/W/forks/F/turns/N/ts/S'
  turn_id   TEXT NOT NULL REFERENCES turns(id),
  position  INTEGER NOT NULL,           -- S
  UNIQUE (turn_id, position)
);

CREATE TABLE files (
  id      TEXT PRIMARY KEY,             -- 'windows/W/forks/F/turns/N/ts/S/src/<path>'
  t_id    TEXT NOT NULL REFERENCES ts(id),
  path    TEXT NOT NULL,                -- relative to the T's src/
  content TEXT NOT NULL,
  UNIQUE (t_id, path)
);

CREATE TABLE test_results (
  id     TEXT PRIMARY KEY,              -- 'windows/W/forks/F/turns/N/ts/S/tests.json#<test>'
  t_id   TEXT NOT NULL REFERENCES ts(id),
  test   INTEGER NOT NULL,              -- test case number in the suite
  stdout TEXT NOT NULL,
  stderr TEXT NOT NULL,
  passed INTEGER NOT NULL,
  status TEXT NOT NULL,
  UNIQUE (t_id, test)
);

CREATE TABLE generations (
  id TEXT PRIMARY KEY,
  turn_id TEXT NOT NULL REFERENCES turns(id),
  position INTEGER NOT NULL
);

CREATE TABLE feedback (
  turn_id TEXT PRIMARY KEY REFERENCES turns(id)
);
