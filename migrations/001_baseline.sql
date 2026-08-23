-- Baseline schema. Existing SCHEMA constant in store.py is idempotent
-- (CREATE TABLE IF NOT EXISTS), and this file records that as migration 1
-- so newer numbered files can ALTER on top of it without re-running the
-- baseline every boot.
--
-- No statements here on purpose: store.py's executescript(SCHEMA) already
-- handled this on every existing box. Adding CREATE statements would
-- cause "table already exists" errors on those boxes.
SELECT 1;
