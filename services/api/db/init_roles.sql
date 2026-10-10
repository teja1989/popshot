-- Creates the two database roles for local development and CI.
-- In Google Cloud the same roles are created by infrastructure code, never by migrations.
--
-- Run as a superuser with passwords passed in, for example:
--   psql -v ON_ERROR_STOP=1 -v owner_password="$OWNER_PW" -v app_password="$APP_PW" \
--        -f db/init_roles.sql "$ADMIN_URL"
--
-- popshot_owner: runs migrations and owns every table and function. Not a superuser.
-- popshot_app:   what the API connects as. Owns nothing, cannot bypass RLS, cannot create
--                roles or databases, and is not a member of any other role.

CREATE ROLE popshot_owner LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION
  PASSWORD :'owner_password';
CREATE ROLE popshot_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION
  NOINHERIT PASSWORD :'app_password';

CREATE DATABASE popshot OWNER popshot_owner;
REVOKE ALL ON DATABASE popshot FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE popshot TO popshot_owner;
GRANT CONNECT ON DATABASE popshot TO popshot_app;

\connect popshot
-- Only the owner may create objects in the public schema.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO popshot_owner;
GRANT USAGE ON SCHEMA public TO popshot_app;
