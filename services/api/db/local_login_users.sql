-- Creates the two login users for local development and CI. On Cloud SQL these are the
-- service accounts' IAM database users instead, and no passwords exist.
--
-- Run as a superuser, then run the bootstrap (see services/api/README.md):
--   psql -v ON_ERROR_STOP=1 -v migrator_password="$PW1" -v api_password="$PW2" \
--        -f db/local_login_users.sql "$ADMIN_URL"

CREATE ROLE popshot_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION
  PASSWORD :'migrator_password';
CREATE ROLE popshot_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION
  PASSWORD :'api_password';
