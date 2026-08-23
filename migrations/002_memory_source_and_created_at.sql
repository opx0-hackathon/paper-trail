-- Add columns older boxes never had. IF NOT EXISTS on ALTER isn't a thing
-- in SQLite, so the runner in store.py checks PRAGMA table_info before it
-- calls this file — nothing to guard here.
ALTER TABLE memories ADD COLUMN source     TEXT NOT NULL DEFAULT 'seeded';
ALTER TABLE memories ADD COLUMN created_at REAL NOT NULL DEFAULT 0;
