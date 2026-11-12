-- Turn paths used by runSummary. all other artifacts are read directly.
CREATE TABLE turns (
  id       TEXT PRIMARY KEY,            -- 'windows/W/forks/F/turns/N'
  fork_id  TEXT NOT NULL,
  position INTEGER NOT NULL,            -- N
  UNIQUE (fork_id, position)
);
