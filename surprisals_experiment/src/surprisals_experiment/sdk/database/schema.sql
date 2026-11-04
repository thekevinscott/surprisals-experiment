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

CREATE TABLE advice (
  id         TEXT PRIMARY KEY,          -- 'windows/W/forks/F/turns/N/advice.txt'
  turn_id    TEXT NOT NULL UNIQUE REFERENCES turns(id),
  text       TEXT NOT NULL,
  score      NUMERIC NOT NULL,          -- chars, or total bits
  score_text TEXT,                      -- per-token bits rendering, NULL in chars mode
  rejected   INTEGER NOT NULL
);

CREATE TABLE ts (
  id        TEXT PRIMARY KEY,           -- 'windows/W/forks/F/turns/N/ts/S'
  advice_id TEXT NOT NULL REFERENCES advice(id),
  position  INTEGER NOT NULL,           -- S
  UNIQUE (advice_id, position)
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
