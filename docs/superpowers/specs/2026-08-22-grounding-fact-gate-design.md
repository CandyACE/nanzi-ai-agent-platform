# 刷新模式事实接地门控设计

## 目标

在刷新/动态数据请求中，只阻断没有新鲜、相关证据支撑的事实性断言；对明确拒答、暂无结果、澄清问题、假设示例和非事实性过程说明放行，避免把安全回复误报为高风险幻觉。

## 当前根因

`FactRequirement.block_unsupported_facts` 只表达“未验证事实需要阻断”，但当前工作树将它直接用于陈旧证据、内部兼容证据和缺失证据三个分支，没有先判断候选回答是否包含事实性断言。因此，刷新模式下“我暂时无法读取运行状态”也会得到 `BLOCK_UNGROUNDED_FACTS + HIGH`。

## 设计

### 1. 候选回答分类边界

继续复用 `policy.py` 已有的事实信号识别：

- `contains_grounding_fact_signal(text)` / `_contains_structural_external_fact(text)` 命中数字、排名、实时状态、执行结果、具体实体结论等事实信号时，视为事实性回答。
- 未命中事实信号的回答，在刷新模式下视为安全非事实回答，直接放行。
- 明确“无法读取、暂无结果、未查询”等拒答文本仍需保持无事实约束；若同时包含具体数字或实体结论，仍视为事实性回答并进入阻断策略。
- 假设、示例、创作和数学推导沿用现有识别规则，不因刷新模式被阻断。

### 2. 证据决策

- `block_unsupported_facts=False`：保持现有低/中/高风险软提示分层，不改变普通请求行为。
- `block_unsupported_facts=True` 且回答非事实性：直接 `PASS`，不追加高风险提示。
- `block_unsupported_facts=True` 且回答为事实性：
  - 新鲜且相关证据存在时 `PASS`；
  - 证据陈旧、类型不匹配或缺失时保留回答并返回 `PASS_WITH_WARNING + HIGH`，让用户自行判断；当前标准路径不主动硬阻断。
- 继续保留“明确无结果且没有具体事实”的安全放行路径。

### 3. 改动边界

只调整 `app/services/ai/grounding/policy.py` 的候选回答门控和风险动作，以及对应单测，并更新 `tests/CHECKLIST.md` 的语义描述。保持 runner、工具权限、证据账本格式、API 和前端协议不变。

## 测试策略

在 `tests/ai/grounding/test_grounding_policy.py` 增加以下回归矩阵：

1. 刷新模式 + 陈旧证据 + 具体事实 → `PASS_WITH_WARNING/HIGH`。
2. 刷新模式 + 陈旧证据 + 拒答/澄清 → `PASS/NONE`。
3. 刷新模式 + 内部兼容证据 + 具体事实 → `PASS_WITH_WARNING/HIGH`。
4. 刷新模式 + 内部兼容证据 + 非事实说明 → `PASS/NONE`。
5. 刷新模式 + 缺失证据 + 具体事实 → `PASS_WITH_WARNING/HIGH`。
6. 刷新模式 + 缺失证据 + 非事实说明 → `PASS/NONE`。
7. 普通模式下既有 warning 分层测试保持通过。

## 非目标

- 不把所有无法验证的自然语言都改成硬拒答。
- 不重写事实信号正则、请求路由或证据账本。
- 不将当前服务层的 `BLOCK` 改成前端不可见的硬拦截；现有用户提示链保持不变。
