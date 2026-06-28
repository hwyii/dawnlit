CREATE TABLE IF NOT EXISTS profiles (
  id TEXT PRIMARY KEY,
  payload TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
  id TEXT PRIMARY KEY,
  paper_id TEXT NOT NULL,
  action TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  abstract TEXT NOT NULL DEFAULT '',
  topics TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_paper_id ON feedback(paper_id);
