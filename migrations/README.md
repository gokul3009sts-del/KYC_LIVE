# Migrations

The project now uses PostgreSQL. The schema is created directly from the
SQLAlchemy models (`Base.metadata.create_all`) when the app first starts,
so these MySQL files are no longer used.

- `mysql_legacy/` — the original MySQL DDL, kept for reference only.
  Do not run these against PostgreSQL; the syntax is incompatible.

To load the converted schema and data, use the dump in the project root:

    psql -U nbaworld -d nbaworld_db -f nbaworld_db_postgres.sql
