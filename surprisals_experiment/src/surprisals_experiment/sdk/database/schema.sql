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
  score      NUMERIC,                   -- chars, or total bits
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

CREATE VIEW evaluated_turns AS
WITH tested AS (
  SELECT ts.turn_id, ts.position, coalesce(min(test_results.passed), 0) AS passed
  FROM ts LEFT JOIN test_results ON test_results.t_id = ts.id GROUP BY ts.id
)
SELECT turns.id, windows.position AS window, forks.position AS fork, turns.position AS turn,
       advices.text, advices.score, advices.score_text, count(*) AS samples, min(tested.passed) AS passed
FROM windows JOIN forks ON forks.window_id = windows.id
JOIN turns ON turns.fork_id = forks.id
JOIN turn_advice ON turn_advice.turn_id = turns.id
JOIN advices ON advices.id = turn_advice.advice_id
JOIN tested ON tested.turn_id = turns.id
GROUP BY turns.id;

CREATE TABLE generations (
  id TEXT PRIMARY KEY,
  turn_id TEXT NOT NULL REFERENCES turns(id),
  position INTEGER NOT NULL
);

CREATE TABLE feedback (
  turn_id TEXT PRIMARY KEY REFERENCES turns(id)
);

CREATE VIEW ready_turns AS
SELECT evaluated_turns.* FROM evaluated_turns
WHERE score IS NOT NULL AND NOT EXISTS (
  SELECT 1 FROM ts LEFT JOIN generations ON generations.id = ts.id
  WHERE ts.turn_id = evaluated_turns.id AND generations.id IS NULL
);

CREATE VIEW complete_turns AS
SELECT ready_turns.* FROM ready_turns JOIN feedback ON feedback.turn_id = ready_turns.id;
