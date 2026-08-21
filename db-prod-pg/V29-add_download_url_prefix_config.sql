-- V29: 将生成文件下载地址前缀纳入系统配置（PostgreSQL）
INSERT INTO "system_configs"
    ("key", "value", "description", "category", "is_secret")
VALUES
    (
        'download_url_prefix',
        '',
        '生成文件下载地址的公网前缀。只填写协议和域名（例如 https://your-domain.example.com），不要填写 /api/v1/chat/generated-files 路径；留空时回退 APP_PUBLIC_URL 或相对地址。',
        'general',
        FALSE
    )
ON CONFLICT ("key") DO UPDATE
SET
    "description" = EXCLUDED."description",
    "category" = EXCLUDED."category",
    "is_secret" = EXCLUDED."is_secret",
    "updated_at" = CURRENT_TIMESTAMP;
