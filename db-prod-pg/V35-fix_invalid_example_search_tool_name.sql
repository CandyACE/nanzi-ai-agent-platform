-- V35: 修正问答经验检索工具名称，使其符合 OpenAI 兼容工具名规范
-- 工具名仅允许字母、数字、下划线和连字符。

-- 若合法名称已存在，先删除历史错误名称，避免唯一约束冲突。
DELETE FROM "sys_api_tools" AS invalid_tool
WHERE invalid_tool."name" = '检索问答经验库 (search_qa_examples)'
  AND EXISTS (
      SELECT 1
      FROM "sys_api_tools" AS existing_tool
      WHERE existing_tool."name" = 'search_qa_examples'
        AND existing_tool."id" <> invalid_tool."id"
  );

UPDATE "sys_api_tools"
SET "name" = 'search_qa_examples'
WHERE "name" = '检索问答经验库 (search_qa_examples)';
