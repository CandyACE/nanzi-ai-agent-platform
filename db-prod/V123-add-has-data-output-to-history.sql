-- V123: 会话历史持久化“结构化输出标记”。AI 执行记录落库时
-- 明确记录该轮是否产出了数据表格/文件等结构化输出，供看板与历史
-- 回放统一使用布尔语义，消除“字段缺失即无输出”的歧义。
ALTER TABLE `ai_agent_execution_history`
  ADD COLUMN `has_data_output` INT(11) NOT NULL DEFAULT 0 COMMENT '是否产出了数据表格/文件等结构化输出' AFTER `total_tokens`;