# PostgreSQL V5 Tool Seeds Implementation Plan

**Goal:** Restore the 11 PostgreSQL `sys_api_tools` seed rows that are present in the MySQL migration history and are required by the agent tool selector.

**Architecture:** Keep the existing V5 filename and make it a consolidated, idempotent PostgreSQL seed migration. It inserts the four generic HTTP tools, three Jira tools, three notification tools, and `search_qa_examples`; existing rows with the same tool name are preserved. No frontend or runtime registry changes are needed.

**Tech Stack:** PostgreSQL SQL, pytest contract tests, existing `db-prod-pg/apply_sql.py` importer.

---

### Task 1: Define the V5 tool-seed contract

**Files:**
- Modify: `tests/test_pg_prod_apply_sql.py:249-255`

- [ ] **Step 1: Assert V5 exists and contains all 11 expected tool names.**
- [ ] **Step 2: Assert the migration uses PostgreSQL boolean syntax and name-based idempotency.**
- [ ] **Step 3: Run the focused test and confirm it fails because the current V5 file is absent.**

### Task 2: Restore the consolidated PostgreSQL V5 migration

**Files:**
- Create: `db-prod-pg/V5-register_example_search_tool.sql`

- [ ] **Step 1: Insert the four generic tools from MySQL V19.**
- [ ] **Step 2: Insert the three Jira tools from MySQL V28/V37.**
- [ ] **Step 3: Insert the three notification tools from MySQL V41/V42/V91.**
- [ ] **Step 4: Insert `search_qa_examples` from MySQL V107.**
- [ ] **Step 5: Use stable PostgreSQL-safe IDs, `TRUE`, `CURRENT_TIMESTAMP`, and `ON CONFLICT (\"name\") DO NOTHING`.**

### Task 3: Verify the migration and preserve the existing worktree boundary

**Files:**
- No additional files.

- [ ] **Step 1: Run the focused V5 contract test and the full `tests/test_pg_prod_apply_sql.py` file.**
- [ ] **Step 2: Run `git diff --check`.**
- [ ] **Step 3: Review the final diff to confirm only the requested V5/test/plan files were added or changed by this task.**
