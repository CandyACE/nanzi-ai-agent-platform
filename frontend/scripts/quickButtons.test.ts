import assert from "node:assert/strict";
import { parseQuickButtons } from "../src/utils/quickButtons.ts";

const sqlTarget = "改用 meta_changelog 表查询 2-7 月每月用户数 AS month, COUNT(DISTINCT user_id) AS monthly_users FROM meta_changelog";
const rendered = parseQuickButtons(`[⚡ 🧙 改用 meta_changelog 表查询 2-7 月每月用户数](quick:${sqlTarget})`);

assert.equal(rendered.includes("quick-action-btn"), true);
assert.equal(rendered.includes("AS monthly_users FROM meta_changelog"), false);
assert.equal(rendered.match(/quick-action-btn/g)?.length, 1);
