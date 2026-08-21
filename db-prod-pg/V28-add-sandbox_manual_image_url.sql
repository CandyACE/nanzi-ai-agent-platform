-- V28: 配置 Docker daemon 不可用时的 AgentScope 预构建镜像下载地址（PostgreSQL）
-- 下载地址应指向 docker save 导出的镜像包（.tar 或 .tar.gz），不得指向任意 Dockerfile。
INSERT INTO "system_configs" ("key", "value", "description", "category", "is_secret")
VALUES (
    'sandbox_docker_manual_image_url',
    '',
    'Docker daemon 不可用时，下载符合 AgentScope 规范的预构建镜像包（docker save 导出的 tar/tar.gz）的地址。',
    'sandbox',
    FALSE
)
ON CONFLICT ("key") DO UPDATE
SET
    "description" = EXCLUDED."description",
    "category" = EXCLUDED."category",
    "is_secret" = EXCLUDED."is_secret",
    "updated_at" = CURRENT_TIMESTAMP;
