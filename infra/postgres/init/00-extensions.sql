-- Runs once, on first initialisation of the data volume.
-- Extensions are also created (IF NOT EXISTS) by migration 0001, so this file
-- only makes them available in template1 for databases created later (e.g. the test DB).
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

\connect template1
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
