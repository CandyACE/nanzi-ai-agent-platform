# 推荐指标详情弹窗 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在智能指标发现结果中为单个推荐指标增加详情弹窗，同时保留卡片点击勾选和批量保存行为。

**Architecture:** 详情状态保留在 `SmartMetricModal.vue` 内，直接复用当前 `recommendations` 数组，不增加 API 请求或后端字段。推荐卡片主体继续调用 `toggleSelection`；右上角新增独立的详情按钮，通过 `@click.stop` 避免改变选中状态；详情弹窗在同一外层弹窗内以更高层级展示，关闭后恢复列表状态。

**Tech Stack:** Vue 3 `<script setup>`、TypeScript、Tailwind CSS、pytest 前端契约测试、Vite 构建。

---

### Task 1: 为详情交互补充失败契约测试

**Files:**
- Modify: `tests/frontend/test_smart_metric_modal_contract.py`
- Test target: `frontend/src/components/metadata/SmartMetricModal.vue`

- [x] **Step 1: 写入失败测试**

在现有 `test_smart_metric_modal_contract` 末尾增加以下断言，明确要求详情状态、打开/关闭函数、事件隔离和完整字段展示：

```python
    # 6. 推荐指标单项详情弹窗契约
    assert "selectedRecommendationIndex" in content
    assert "openRecommendationDetail" in content
    assert "closeRecommendationDetail" in content
    assert "查看详情" in content
    assert "@click.stop=\"openRecommendationDetail(idx)\"" in content
    assert "item.calculation_logic" in content
    assert "item.description" in content
    assert "item.tags" in content
```

- [x] **Step 2: 运行测试确认按预期失败**

运行：

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_smart_metric_modal_contract.py -q
```

预期：失败，提示 `selectedRecommendationIndex` 或 `openRecommendationDetail` 尚不存在；这证明测试确实捕获了待实现行为。

### Task 2: 实现推荐指标详情状态与入口

**Files:**
- Modify: `frontend/src/components/metadata/SmartMetricModal.vue`

- [x] **Step 1: 增加详情状态与最小操作函数**

在 `selectedIndices` 状态附近增加：

```ts
const selectedRecommendationIndex = ref<number | null>(null)

const selectedRecommendation = computed(() => {
  if (selectedRecommendationIndex.value === null) return null
  return recommendations.value[selectedRecommendationIndex.value] || null
})

const openRecommendationDetail = (index: number) => {
  selectedRecommendationIndex.value = index
}

const closeRecommendationDetail = () => {
  selectedRecommendationIndex.value = null
}
```

- [x] **Step 2: 在列表重置路径清理详情状态**

在 `handleRecommend` 开始清空结果、`handleBackToConfig` 和 `handleClose` 中同步设置：

```ts
selectedRecommendationIndex.value = null
```

这样重新生成、返回配置和关闭外层弹窗时不会保留失效索引。

- [x] **Step 3: 增加独立“查看详情”按钮**

在推荐卡片右上角勾选圆形控件旁加入带 `@click.stop="openRecommendationDetail(idx)"` 的“查看详情”按钮；保留卡片主体 `@click="toggleSelection(idx)"` 和勾选控件行为。按钮桌面端显示文字，窄屏隐藏文字但保留图标与 `title="查看指标完整详情"`。

- [x] **Step 4: 增加详情弹窗**

在外层 `SmartMetricModal` 根节点结束前、帮助弹窗之前增加 `v-if="selectedRecommendation"` 的 `z-[60]` 弹窗：

```vue
<div class="fixed inset-0 z-[60] ..." @click.self="closeRecommendationDetail">
  <div class="... max-w-2xl ...">
    <header>
      <p>推荐指标详情</p>
      <h3>{{ selectedRecommendation.display_name }}</h3>
      <code>#{{ selectedRecommendation.name }}</code>
      <span v-if="selectedRecommendation.unit">{{ selectedRecommendation.unit }}</span>
      <button type="button" @click="closeRecommendationDetail" title="关闭详情">关闭</button>
    </header>
    <main class="overflow-y-auto">
      <section>
        <h4>业务描述</h4>
        <p>{{ selectedRecommendation.description || '暂无描述' }}</p>
      </section>
      <section>
        <h4>计算逻辑 / SQL</h4>
        <pre>{{ selectedRecommendation.calculation_logic || '--' }}</pre>
      </section>
      <section v-if="selectedRecommendation.tags && selectedRecommendation.tags.length">
        <h4>标签</h4>
        <span v-for="tag in selectedRecommendation.tags" :key="tag">{{ tag }}</span>
      </section>
    </main>
    <footer><button type="button" @click="closeRecommendationDetail">关闭</button></footer>
  </div>
</div>
```

详情弹窗不提供单独保存按钮，保存仍由底层列表的“保存选中指标”统一处理；长 SQL 放在 `pre` 的可滚动容器内，避免撑破弹窗。

### Task 3: 回归验证与提交

**Files:**
- Verify: `frontend/src/components/metadata/SmartMetricModal.vue`
- Verify: `tests/frontend/test_smart_metric_modal_contract.py`

- [x] **Step 1: 运行详情契约和相关前端契约测试**

运行：

```bash
pytest --confcutdir=tests/frontend tests/frontend/test_smart_metric_modal_contract.py tests/frontend/test_metadata_flow_guide_contract.py -q
```

预期：全部通过。

- [x] **Step 2: 执行前端构建**

运行：

```bash
cd frontend && npm run build
```

预期：Vite 构建成功；既有 Browserslist、动态/静态导入或 chunk 体积提示记录为 warning，不作为本功能失败。

- [x] **Step 3: 检查差异并提交**

运行：

```bash
git diff --check
git status --short
git add frontend/src/components/metadata/SmartMetricModal.vue tests/frontend/test_smart_metric_modal_contract.py
git commit -m "feat: 增加推荐指标详情弹窗"
```

预期：只包含组件与契约测试的功能提交；设计文档和实施计划作为已提交文档保留。
