# Embed 智能体路由偏好 Implementation Plan

> **For agentic workers:** Implement the tasks in order and keep the user's no-commit boundary. Do not run service startup or deployment scripts.

**Goal:** Add Redis-persisted Embed routing preferences for automatic routing or a user-selected default agent, while hiding and enforcing the route when an integration supplies `agent_id`.

**Architecture:** Extend the existing per-user portal preference JSON with routing fields and add a narrow routing update endpoint. Load the preference before normal Embed agent selection, validate it against the already-authorized agent list, and expose a settings group that is omitted whenever the current Embed instance is integration-locked.

**Tech Stack:** FastAPI, Pydantic 2, Redis, Vue 3, TypeScript, pytest, frontend contract tests.

---

### Task 1: Add backend routing preference contract

**Files:**
- Modify: `app/api/portal/endpoints/portal_prefs.py`
- Test: `tests/api/portal/test_portal_prefs.py`

- [ ] Add `routing_mode` and `expert_agent_id` to the portal preference model with `auto` as the default.
- [ ] Add a routing update request model that accepts only `auto` or `expert` and normalizes the agent ID.
- [ ] Preserve all unrelated fields when the routing endpoint reads and writes the existing Redis JSON.
- [ ] Reject `expert` without an agent ID and reject an unavailable or unauthorized agent before persistence.
- [ ] Add tests for defaults, round-trip persistence, unrelated-field preservation, invalid mode, missing agent, and permission denial.

### Task 2: Load and save routing preferences in Embed

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue`
- Test: `tests/frontend/test_embed_routing_preference_contract.py`

- [ ] Add a typed routing preference state and load it through `/api/portal/portal-prefs` during the existing allowed-agent initialization.
- [ ] Make Redis the routing preference source of truth and stop reading/writing the old unscoped routing `localStorage` keys.
- [ ] Apply `expert` only when the saved agent is present in the current allowed-agent list; otherwise fall back to `auto`.
- [ ] Save ordinary user changes through `PUT /api/portal/portal-prefs/routing`.
- [ ] Keep integration-selected agent IDs session-scoped and prevent them from overwriting Redis defaults.
- [ ] Add contract assertions for GET loading, routing PUT payloads, fallback behavior, and normal send payload selection.

### Task 3: Add settings UI and lock visibility

**Files:**
- Modify: `frontend/src/components/embed/ChatSettings.vue`
- Modify: `frontend/src/views/EmbedChat.vue`
- Test: `tests/frontend/test_embed_routing_preference_contract.py`

- [ ] Add `routingMode`, `expertAgentId`, `routingLocked`, and `allowedAgents` bindings to the settings component.
- [ ] Render the two-tab routing group using the existing settings visual language.
- [ ] Emit route changes to the parent and save only ordinary user changes.
- [ ] Hide the whole group when the Embed instance is locked by URL, INIT_CONFIG, or Ticket `agent_id`.
- [ ] Ensure locked initialization cannot call the ordinary preference-saving path.

### Task 4: Cover integration lock precedence

**Files:**
- Modify: `frontend/src/views/EmbedChat.vue`
- Test: `tests/frontend/test_embed_url_agent_lock_contract.py`
- Test: `tests/frontend/test_embed_routing_preference_contract.py`

- [ ] Track the lock source explicitly for URL, INIT_CONFIG, and Ticket agent IDs.
- [ ] Enforce integration lock over Redis preferences and UI changes.
- [ ] Assert that locked instances send the integration agent and never fall back to automatic routing.
- [ ] Assert that the integration agent is not persisted as the user's default preference.

### Task 5: Run focused verification

**Files:**
- Test: `tests/api/portal/test_portal_prefs.py`
- Test: `tests/frontend/test_embed_routing_preference_contract.py`
- Test: `tests/frontend/test_embed_url_agent_lock_contract.py`

- [ ] Run `pytest --confcutdir=tests/frontend tests/api/portal/test_portal_prefs.py tests/frontend/test_embed_routing_preference_contract.py tests/frontend/test_embed_url_agent_lock_contract.py -q`.
- [ ] Run `python3 -m compileall app/api/portal/endpoints/portal_prefs.py`.
- [ ] Run `git diff --check` on the scoped changes.
- [ ] Report tests and any pre-existing unrelated failures; do not stage or commit.
