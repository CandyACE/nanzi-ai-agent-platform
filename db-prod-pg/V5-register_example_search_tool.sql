INSERT INTO sys_api_tools (id, name, description, method, url_template, is_active, created_at, updated_at)
VALUES (
    'search_qa_examples',
    '检索问答经验库 (search_qa_examples)',
    '检索已验证的历史问答优质案例及 SQL，用于参考同类指标的计算口径或表关联。',
    'POST',
    '/api/sys/tools/search_qa_examples',
    1,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
ON CONFLICT (id) DO NOTHING;
