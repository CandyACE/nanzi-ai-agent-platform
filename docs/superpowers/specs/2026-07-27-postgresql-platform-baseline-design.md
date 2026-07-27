# PostgreSQL Platform Baseline Design

## Scope

This change adds a PostgreSQL-first-install path on branch `codex/pg-database-support` while preserving the existing MySQL migration chain under `db-prod/`.

The PostgreSQL path will provide:

- `db-prod-pg/V0-baseline.sql`, representing the current platform schema and required bootstrap data rather than a one-to-one translation of all historical MySQL migrations.
- A PostgreSQL-aware Python importer with explicit connection arguments, safe database creation, transactional execution, repeatable bootstrap behavior, and clear failure reporting.
- A shell entrypoint and PostgreSQL deployment documentation.
- Contract tests for SQL inventory, importer argument handling, database-name safety, statement splitting, and idempotent seed conventions.

This change does not migrate existing MySQL production data and does not modify the current `db-prod/V*.sql` files.

## Design

The baseline is a single current-state schema. Historical MySQL-only operations such as `AUTO_INCREMENT`, `ENGINE=InnoDB`, `ON DUPLICATE KEY UPDATE`, `INSERT IGNORE`, MySQL identifier quoting, and MySQL partition DDL are converted into PostgreSQL equivalents or represented by the final desired state. Future schema changes must add paired MySQL and PostgreSQL migrations, or later move both paths behind a common migration framework.

The importer uses psycopg's synchronous client because deployment is an offline command-line workflow. It connects to a maintenance database with autocommit to create the target database when needed, then opens a transaction against the target database and executes the baseline statements. Database identifiers are always passed through `psycopg.sql.Identifier`; SQL values remain parameterized where applicable.

The baseline uses PostgreSQL-native identity columns, `jsonb` for platform JSON payloads, `bytea` for scheduler job state, `timestamp without time zone` for existing application timestamps, and ordinary PostgreSQL indexes/constraints. Log retention is represented by the tables and indexes only; the existing MySQL partition maintenance job is outside this baseline and will be handled by the later dual-runtime work.

## Verification

- Run the importer contract tests without a live database.
- Parse the baseline with a PostgreSQL parser or psycopg-compatible validation where available.
- If a PostgreSQL service is supplied by the user, run the importer twice and verify table, index, seed, and row-count invariants.
- Run `git diff --check` and keep the existing MySQL test suite unchanged.
