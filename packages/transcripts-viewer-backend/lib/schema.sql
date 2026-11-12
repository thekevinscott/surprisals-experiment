-- Copied from packages/run_database/src/run_database/schema.sql.
-- Viewer adaptation: tolerate partial live writes (no foreign-key enforcement),
-- keep test cases per attempt, derive samples from attempts, and evaluate the latest retry.
CREATE TABLE windows (
  id       TEXT PRIMARY KEY,            -- 'windows/W'
  position INTEGER NOT NULL UNIQUE      -- W, for ordering
);

CREATE TABLE forks (
  id        TEXT PRIMARY KEY,           -- 'windows/W/forks/F'
  window_id TEXT NOT NULL,
  position  INTEGER NOT NULL,           -- F
  UNIQUE (window_id, position)
);

CREATE TABLE turns (
  id       TEXT PRIMARY KEY,            -- 'windows/W/forks/F/turns/N'
  fork_id  TEXT NOT NULL,
  position INTEGER NOT NULL,            -- N
  UNIQUE (fork_id, position)
);

CREATE TABLE advices (
  id         TEXT PRIMARY KEY,          -- 'advices/<sha256>'
  text       TEXT NOT NULL UNIQUE,
  score      NUMERIC,          -- chars, or total bits
  score_text TEXT                       -- per-token bits rendering, NULL in chars mode
);

CREATE TABLE turn_advice (
  turn_id   TEXT NOT NULL UNIQUE,
  advice_id TEXT NOT NULL
);

-- Samples are derived from their attempts so deleting/replacing a retry cannot
-- remove the sample row contributed by an earlier attempt.
CREATE VIEW ts AS
SELECT DISTINCT substr(id, 1, instr(id, '/attempts/') - 1) AS id,
       turn_id, sample AS position
FROM t_attempts WHERE exit_code IS NOT NULL AND exit_code <> -1;

CREATE TABLE t_attempts (
  id        TEXT PRIMARY KEY,           -- 'windows/W/forks/F/turns/N/ts/S/attempts/A'
  turn_id   TEXT NOT NULL,
  sample    INTEGER NOT NULL,           -- S
  position  INTEGER NOT NULL,           -- A
  exit_code INTEGER,                    -- NULL when timed out
  timed_out INTEGER NOT NULL,
  UNIQUE (turn_id, sample, position)
);

CREATE TABLE files (
  id         TEXT PRIMARY KEY,          -- 'windows/W/forks/F/turns/N/ts/S/attempts/A/src/<path>'
  attempt_id TEXT NOT NULL,
  path       TEXT NOT NULL,             -- relative to the attempt's src/
  content    TEXT NOT NULL,
  UNIQUE (attempt_id, path)
);

CREATE TABLE test_results (
  id     TEXT PRIMARY KEY,              -- 'windows/W/forks/F/turns/N/ts/S/attempts/A/tests.json#<test>'
  t_id   TEXT NOT NULL,
  attempt_id TEXT NOT NULL,
  test   INTEGER NOT NULL,              -- test case number in the suite
  stdout TEXT NOT NULL,
  stderr TEXT NOT NULL,
  passed INTEGER NOT NULL,
  status TEXT NOT NULL,
  UNIQUE (attempt_id, test)
);

CREATE VIEW evaluated_turns AS
WITH latest AS (
  SELECT turn_id, sample, max(position) AS position FROM t_attempts GROUP BY turn_id, sample
), tested AS (
  SELECT ts.turn_id, ts.position,
         CASE WHEN a.timed_out OR a.exit_code IS NULL OR a.exit_code <> 0
              THEN 0 ELSE coalesce(min(test_results.passed), 0) END AS passed
  FROM ts JOIN latest ON latest.turn_id = ts.turn_id AND latest.sample = ts.position
  JOIN t_attempts a ON a.turn_id = latest.turn_id AND a.sample = latest.sample AND a.position = latest.position
  LEFT JOIN test_results ON test_results.attempt_id = a.id
  GROUP BY ts.id
)
SELECT turns.id, windows.position AS window, forks.position AS fork, turns.position AS turn,
       advices.text, advices.score, advices.score_text, count(*) AS samples, min(tested.passed) AS passed
FROM windows JOIN forks ON forks.window_id = windows.id
JOIN turns ON turns.fork_id = forks.id
JOIN turn_advice ON turn_advice.turn_id = turns.id
JOIN advices ON advices.id = turn_advice.advice_id
JOIN tested ON tested.turn_id = turns.id
WHERE advices.score IS NOT NULL
GROUP BY turns.id;
