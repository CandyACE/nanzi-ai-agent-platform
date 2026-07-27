-- V1: 对齐 MySQL 迁移链中的系统配置种子数据
--
-- 说明：
-- 1. 补齐 V0 基线遗漏的系统配置，覆盖 Agent、Metadata、Data API、Knowledge、Other
--    以及品牌个性化配置。
-- 2. 修正 V0 中与 MySQL V68 不一致的配置分类。
-- 3. 冲突时只更新配置元数据，不覆盖已有部署的 value，避免升级时丢失环境配置。

INSERT INTO "system_configs" ("key", "value", "description", "category", "is_secret") VALUES
    ('ragflow_similarity_threshold', '0.4', 'RAGFlow 语义检索的最低相似度阈值 (0-1)，越低召回率越高但越不精准', 'metadata', FALSE),
    ('ragflow_vector_weight', '0.85', 'RAGFlow 混合检索中向量检索的权重 (0-1)，剩余为全文检索权重', 'metadata', FALSE),
    ('external_sql_data_source', 'default_clickhouse', '外部 SQL 执行数据源 ID (Data Source ID)', 'data_api', FALSE),
    ('agent_max_context_messages', '20', '发送给 LLM 的最大历史消息条目数 (建议 10-30, 20条约10轮对话)', 'agent', FALSE),
    ('chatbi_sample_similarity_threshold', '0.4', 'ChatBI 经验库检索相似度阈值 (0-1)，建议 0.4。只有高于此分值的案例才会被注入 Prompt。', 'data_api', FALSE),
    ('chatbi_sample_vector_similarity_weight', '0.85', 'ChatBI 经验库检索向量权重 (0-1)，建议 0.85。剩余权重归于全文检索。', 'data_api', FALSE),
    ('ragflow_metadata_top_k', '8', 'RAGFlow 元数据检索时返回的 Top K 数量，控制 AI 可感知的表结构上限', 'metadata', FALSE),
    ('sql_execution_mode', 'local', 'SQL 执行模式 (remote: 走远程执行服务, local: 本地数据源直连执行, auto/空: 查表动态判断)', 'data_api', FALSE),
    ('embedchat_watermark_enabled', 'false', '是否开启嵌入式对话水印 (true/false)', 'other', FALSE),
    ('embedchat_watermark_style', 'user_time', '水印样式选项 (user_time: 用户名+时间戳, custom: 自定义文字+时间戳)', 'other', FALSE),
    ('embedchat_watermark_text', '南孜系统', '水印自定义文字内容 (选为自定义文字时仍会自动附加当前时间戳)', 'other', FALSE),
    ('yovole_sso_enabled', 'false', '控制是否启用 Yovole SSO 统一登录。关闭后，登录页面的 SSO 登录将隐藏，且用户管理中的 SSO 同步按钮也将隐藏。', 'other', FALSE),
    ('embed_api_url', 'https://ds-api.yovole.com/v1', '全局 Embedding 模型 API 地址，本地 HNSW 元数据和案例相似度匹配场景下将用于向量计算', 'agent', FALSE),
    ('embed_api_key', '', '全局 Embedding 模型 API Key', 'agent', TRUE),
    ('embed_model_name', 'bge-m3', '全局 Embedding 模型名称', 'agent', FALSE),
    ('embed_dimensions', '1024', '全局 Embedding 向量维度，必须与 Redis 创建索引设定的维度相匹配', 'agent', FALSE),
    ('chatbi_sample_top_k', '5', 'ChatBI 优质案例相似度检索返回的最大条数', 'data_api', FALSE),
    ('knowledge_ragflow_api_url', '', 'RAGFlow 知识库服务 API 接口网关地址，知识库问答检索将始终使用本节参数', 'knowledge', FALSE),
    ('knowledge_ragflow_api_key', '', '用于调用 RAGFlow 知识库服务的 API Key', 'knowledge', TRUE),
    ('knowledge_ragflow_dataset_ids', '', '默认绑定的知识库 ID（可多选），用于常规智能体问答召回背景知识文档', 'knowledge', FALSE),
    ('knowledge_ragflow_metadata_top_k', '5', '常规知识库问答检索时，最大召回的候选文档片段数量。值越大参考条数越多，但会增加 Token 消耗。', 'knowledge', FALSE),
    ('knowledge_ragflow_similarity_threshold', '0.2', '常规知识库检索时的相似度阈值（0.0 至 1.0）。低于此设定值的检索结果将被过滤，以防混入无关文档，推荐配置为 0.20。', 'knowledge', FALSE),
    ('knowledge_ragflow_vector_weight', '0.3', '常规知识库检索时向量相似度权重的占比（0.0 至 1.0），其余权重为全文关键词匹配。推荐配置为 0.30。', 'knowledge', FALSE),
    ('branding.enabled', 'false', '是否启用品牌个性化', 'branding', FALSE),
    ('branding.product_name', '南孜 · 智能体平台', '产品名称（浏览器标题、侧栏、登录页）', 'branding', FALSE),
    ('branding.login_subtitle', 'NanZi Intelligent Agent Platform', '登录页副标题', 'branding', FALSE),
    ('branding.icon_url', '/favicon.png', 'Logo / Favicon 地址（相对或绝对 URL）', 'branding', FALSE),
    ('branding.hide_login_sso', 'false', '登录页隐藏 SSO 登录', 'branding', FALSE),
    ('branding.hide_version_link', 'false', '侧栏版本号取消 GitHub 外链', 'branding', FALSE),
    ('branding.contact_markdown', '', '联系信息 Markdown（个人中心 → 关于）', 'branding', FALSE),
    ('branding.copyright_text', '', '登录页底部版权文案（启用品牌个性化后展示）', 'branding', FALSE),
    ('third_party_user_sync_config', '{"enabled":false,"connection_config_id":null,"table_name":null,"field_map":{"id":"","user_name":"","real_name":null,"remark":null},"schedule":"off"}', '第三方用户同步配置（数据源、表、字段映射、定时周期）', 'other', FALSE),
    ('knowledge_base_enabled', 'true', '是否启用知识库功能。关闭后，知识库管理、检索测试及智能体知识库检索工具将不可用，下方连接参数仅保留只读。', 'knowledge', FALSE),
    ('llm_model_name', 'DeepSeek-V3.2', '系统默认模型', 'agent', FALSE),
    ('llm_temperature', '0.0', 'LLM 温度参数', 'agent', FALSE),
    ('chatbi_sample_knowledge_base', '', '用于存放用户点赞沉淀的优质 SQL 案例的 RAGFlow 数据集 ID', 'data_api', FALSE)
ON CONFLICT ("key") DO UPDATE
SET
    "description" = EXCLUDED."description",
    "category" = EXCLUDED."category",
    "is_secret" = EXCLUDED."is_secret",
    "updated_at" = CURRENT_TIMESTAMP;
