# Markdown 感知的流式重复检测 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 降低真实模型循环的拦截延迟，同时避免 Markdown 表格、分隔线和代码块被误判为重复输出。

**Architecture:** 在现有流式检测器中增加 Markdown 结构状态与格式行过滤；正文继续做连续句子检测，并增加重复正文块检测。格式内容只保留在输出流中，不参与熔断计数；仅当有效正文形成高置信度连续循环时熔断。

**Tech Stack:** Python 3.11、dataclass、pytest。

---

### Task 1: 锁定 Markdown 与正文循环边界

**Files:**
- Modify: `tests/ai/runtime/test_stream_repetition_detector.py`
- Test: `tests/ai/runtime/test_stream_repetition_detector.py`

- [ ] 新增纯 Markdown 分隔线、表格分隔行、代码块不熔断测试。
- [ ] 新增连续有效句子在较低阈值下熔断测试。
- [ ] 新增重复正文块达到三个周期时熔断测试。
- [ ] 运行测试确认新增用例在现有实现下失败。

### Task 2: 实现 Markdown 感知与双层检测

**Files:**
- Modify: `app/services/ai/runtime/stream_repetition_detector.py`

- [ ] 增加代码围栏状态、Markdown 结构行识别和有效正文归一化。
- [ ] 将句子阈值调整为 12，并忽略短文本、纯格式文本和代码内容。
- [ ] 增加有效正文块的三周期检测，要求块内包含真实文字且长度达到最小值。
- [ ] 保持 `feed`、`reset`、`RepetitionVerdict` 兼容现有调用方。

### Task 3: 回归验证

**Files:**
- Test: `tests/ai/runtime/test_stream_repetition_detector.py`

- [ ] 运行重复检测器专项测试。
- [ ] 运行相关 AgentScope 流式测试。
- [ ] 运行 `git diff --check`。
- [ ] 汇报测试结果与未执行的服务级验证。
