# PostgreSQL Platform Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repeatable PostgreSQL first-install baseline/importer and a selectable dual-database platform runtime on a dedicated branch without changing the existing MySQL migration path.

**Architecture:** Keep `db-prod/` as the MySQL historical migration source. Add a current-state PostgreSQL baseline under `db-prod-pg/`, a psycopg-based offline importer, a small shell wrapper, and a `DATABASE_TYPE`-selected SQLAlchemy runtime. Dialect-sensitive upserts and partition maintenance use explicit MySQL/PostgreSQL branches; common reads and updates use SQLAlchemy expressions.

**Tech Stack:** PostgreSQL SQL, psycopg 3, SQLAlchemy, Python argparse, pytest, shell wrapper.

---

### Task 1: Define the importer contract with failing tests

**Files:**
- Create: `tests/test_pg_prod_apply_sql.py`
- Test: `db-prod-pg/apply_sql.py` after implementation

- [x] **Step 1: Write tests for explicit connection arguments and safe target names.**

  Cover that non-interactive invocation requires `--host`, `--user`, and `--database`; `--port` defaults to `5432`; protected databases such as `postgres`, `template0`, and `template1` are rejected as application targets; and an existing target URL cannot silently redirect the importer to another database.

- [x] **Step 2: Write tests for PostgreSQL statement splitting.**

  Cover semicolons inside single-quoted values, quoted identifiers, PostgreSQL dollar-quoted blocks, line comments, and blank statements. The expected result must preserve complete statements in execution order.

- [x] **Step 3: Run only the new tests and verify the expected RED failure.**

  Run: `.venv/bin/python -m pytest -m no_infrastructure tests/test_pg_prod_apply_sql.py -q`

  Expected: collection or import failure because `db-prod-pg/apply_sql.py` does not exist yet.

### Task 2: Implement the PostgreSQL importer

**Files:**
- Create: `db-prod-pg/apply_sql.py`
- Test: `tests/test_pg_prod_apply_sql.py`

- [x] **Step 1: Add the CLI and validation helpers.**

  Implement `DbConfig`, `parse_args`, `build_config`, `validate_target_database`, and secure prompting. Keep credentials out of logs and require an explicit target database unless `--interactive` is selected.

- [x] **Step 2: Add PostgreSQL-safe database creation.**

  Implement `ensure_database(config)` using a maintenance database connection with `autocommit=True`, query `pg_database`, and create the target through `psycopg.sql.SQL("CREATE DATABASE {}")` plus `psycopg.sql.Identifier(config.database)`. Never interpolate an unvalidated identifier.

- [x] **Step 3: Add transactional baseline execution.**

  Implement `apply_sql(file_path, config)` to read UTF-8 SQL, split statements, execute each statement on the target database, commit only after all statements succeed, and roll back/report the statement number on failure.

- [x] **Step 4: Run the new tests and verify GREEN.**

  Run: `.venv/bin/python -m pytest -m no_infrastructure tests/test_pg_prod_apply_sql.py -q`

  Expected: all importer contract tests pass.

### Task 3: Add the PostgreSQL current-state baseline

**Files:**
- Create: `db-prod-pg/V0-baseline.sql`
- Modify: `tests/test_pg_prod_apply_sql.py`

- [x] **Step 1: Add baseline inventory tests before finalizing SQL.**

  Assert the baseline contains the current platform table set, PostgreSQL-native identity/JSON/blob types, required scheduler table, and no MySQL-only tokens such as `AUTO_INCREMENT`, `ENGINE=InnoDB`, backtick identifiers, `ON DUPLICATE KEY`, or `INSERT IGNORE`.

- [x] **Step 2: Translate the current schema to PostgreSQL current state.**

  Create the tables represented by the latest application models and migration files, including users, agents/versions, metadata, configs/history, audit/history/traces, permissions, tools/MCP, scheduled tasks, knowledge metadata/metrics, ChatBI examples, saved reports/notifications, quota, scenario instances, database profiles, and scheduler job storage. Use PostgreSQL identity columns, `jsonb`, `bytea`, ordinary indexes, foreign keys, and `ON CONFLICT DO NOTHING` only for repeatable bootstrap rows.

- [x] **Step 3: Add current bootstrap data.**

  Include the final current system configuration, built-in agents/versions, generic tools, slash commands, permissions, and other required seed rows from `db-prod/`. Do not replay historical cleanup/update migrations; encode their final desired values once in the baseline.

- [x] **Step 4: Run static baseline tests and parser validation.**

  Run: `.venv/bin/python -m pytest -m no_infrastructure tests/test_pg_prod_apply_sql.py -q`

  Expected: baseline inventory and importer tests pass; any live-database test remains skipped unless PostgreSQL is explicitly available.

### Task 4: Add the deployment entrypoint and documentation

**Files:**
- Create: `db-prod-pg/apply-sql.sh`
- Create: `db-prod-pg/README.md`
- Modify: `tests/test_pg_prod_apply_sql.py`

- [x] **Step 1: Add a shell wrapper.**

  Forward arguments to `.venv/bin/python db-prod-pg/apply_sql.py`, fall back to `venv/bin/python` and then `python3`, and preserve the explicit-argument safety behavior of the Python tool.

- [x] **Step 2: Document fresh PostgreSQL installation.**

  Document PostgreSQL 14+, `psycopg[binary]`, required arguments, interactive mode, repeatable execution, backup expectations, and the fact that this path does not migrate an existing MySQL database.

- [x] **Step 3: Add wrapper contract tests and run the focused suite.**

  Run: `.venv/bin/python -m pytest -m no_infrastructure tests/test_pg_prod_apply_sql.py -q`

  Expected: all tests pass.

### Task 5: Add the selectable dual-database platform runtime

**Files:**
- Modify: `app/core/config.py`, `app/core/orm.py`, `app/main.py`
- Modify: `app/services/config_service.py`, `app/services/knowledge_metrics_service.py`, `app/services/memory_config_service.py`, `app/services/partition_service.py`
- Modify: `app/services/ai/scheduler_service.py`
- Modify: selected operational scripts and Docker/env examples
- Test: `tests/core/test_database_type_config.py`, `tests/services/test_platform_database_dialect_sql.py`

- [x] **Step 1: Add configuration and engine selection.**

  Keep MySQL as the default, allow PostgreSQL-only configuration, and select async ORM, sync APScheduler, and connection error handling from `DATABASE_TYPE`.

- [x] **Step 2: Remove main-platform MySQL-only query assumptions.**

  Compile native upserts for both dialects, use SQLAlchemy expressions for reserved identifiers, and use PostgreSQL-safe ordinary-table pruning while preserving MySQL partition behavior.

- [x] **Step 3: Update operational entrypoints and deployment checks.**

  Route platform scripts through the selected ORM/database configuration, refuse MySQL-only historical DDL under PostgreSQL, and make service readiness checks follow the selected database type.

- [x] **Step 4: Validate both paths.**

  Run focused dialect/config/importer tests, compile changed Python and shell files, and run the PostgreSQL baseline/importer and selected runtime smoke checks against the local PostgreSQL instance.

### Task 6: Final verification and handoff

**Files:**
- Verify: all files created or modified above

- [x] **Step 1: Run focused tests.**

  Run: `.venv/bin/python -m pytest -m no_infrastructure tests/test_pg_prod_apply_sql.py tests/test_postgres_demo_script.py -q`

- [x] **Step 2: Run repository hygiene checks.**

  Run: `git diff --check` and `git status --short --branch`.

- [x] **Step 3: Report the branch, changed files, targeted proof, and live PostgreSQL validation.**
