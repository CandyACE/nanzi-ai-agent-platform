-- V5: 补齐 PostgreSQL 主库的系统 API 工具种子
-- 来源：MySQL V19、V28、V37、V41、V42、V91、V107。
-- 这些工具由前端通过 /api/portal/tools 动态加载；运行时实现仍由 ToolRegistry 提供。

INSERT INTO "sys_api_tools" (
    "id",
    "name",
    "description",
    "method",
    "url_template",
    "headers",
    "parameter_schema",
    "is_active",
    "created_at",
    "updated_at"
) VALUES
(
    'pg-tool-get-current-weather',
    'get_current_weather',
    '获取指定城市的实时天气信息 (使用 wttr.in 服务)',
    'GET',
    'https://wttr.in/{city}?format=j1',
    '{}',
    '{"type":"object","properties":{"city":{"type":"string","description":"城市名称 (支持拼音或英文，如: Shanghai, Beijing)"}},"required":["city"]}',
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),
(
    'pg-tool-get-ip-info',
    'get_ip_info',
    '获取当前执行环境的 IP 地址信息',
    'GET',
    'https://httpbin.org/ip',
    '{}',
    '{"type":"object","properties":{},"required":[]}',
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),
(
    'pg-tool-search-github-repos',
    'search_github_repos',
    '搜索 GitHub 上的开源项目',
    'GET',
    'https://api.github.com/search/repositories?q={query}&sort={sort}&order=desc&per_page=5',
    '{"Accept":"application/vnd.github.v3+json"}',
    '{"type":"object","properties":{"query":{"type":"string","description":"搜索关键词 (e.g. machine learning)"},"sort":{"type":"string","description":"排序方式 (stars, forks, updated)","default":"stars"}},"required":["query"]}',
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),
(
    'pg-tool-get-exchange-rate',
    'get_exchange_rate',
    '获取货币汇率 (使用 frankfurter.app)',
    'GET',
    'https://api.frankfurter.app/latest?from={from_currency}&to={to_currency}',
    '{}',
    '{"type":"object","properties":{"from_currency":{"type":"string","description":"源货币代码 (e.g. USD, EUR, CNY)","default":"USD"},"to_currency":{"type":"string","description":"目标货币代码 (e.g. CNY, JPY)","default":"CNY"}},"required":["from_currency","to_currency"]}',
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),
(
    'pg-tool-jira-search',
    'jira_search',
    'Jira 搜索 (Jira Search): 使用 JQL 语法查询 Jira 历史工单。',
    'POST',
    'internal://jira_search',
    '{}',
    '{}',
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),
(
    'pg-tool-jira-create-issue',
    'jira_create_issue',
    '创建 Jira 工单 (Create Issue): 在 Jira 中创建新的任务或工单。',
    'POST',
    'internal://jira_create_issue',
    '{}',
    '{}',
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),
(
    'pg-tool-jira-get-projects',
    'jira_get_projects',
    '获取 Jira 项目列表 (Get Projects): 查询当前 Jira 系统中可用的项目 Key 和名称。',
    'GET',
    'internal://jira_get_projects',
    '{}',
    '{}',
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),
(
    'pg-tool-send-dingtalk-message',
    'send_dingtalk_message',
    '发送钉钉群机器人 Markdown 消息。自动读取当前用户在个人中心 -> 消息通知里的钉钉 Webhook/加签配置，无需在本轮对话或工具配置中提供 webhook、access_token 或群聊目标。',
    'POST',
    'https://oapi.dingtalk.com/robot/send',
    '{}',
    '{}',
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),
(
    'pg-tool-send-email',
    'send_email',
    '发送邮件通知。自动读取当前用户在个人中心 -> 消息通知里的 SMTP 配置，无需在本轮对话或工具配置中提供 SMTP 服务器或密码。',
    'POST',
    'smtp://send',
    '{}',
    '{}',
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),
(
    'pg-tool-send-wechat-work-message',
    'send_wechat_work_message',
    '发送企业微信群机器人 Markdown 消息。自动读取当前用户在个人中心 -> 消息通知里的企微 Webhook 配置，无需在本轮对话或工具配置中提供 webhook 或群聊目标。',
    'POST',
    'https://qyapi.weixin.qq.com/cgi-bin/webhook/send',
    '{}',
    '{}',
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),
(
    'pg-tool-search-qa-examples',
    'search_qa_examples',
    '检索已验证的历史问答优质案例及 SQL，用于参考同类指标的计算口径或表关联。',
    'POST',
    '/api/sys/tools/search_qa_examples',
    '{}',
    '{}',
    TRUE,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
ON CONFLICT ("name") DO NOTHING;
