-- V127: 添加安全沙箱（sandbox_policy）相关系统配置项，含 Docker 镜像预构建标记（MySQL 方言）
-- 说明：
-- 1. 本脚本合并原 V127（sandbox_policy 及 Docker/E2B/SSH 各策略配置项）与原 V128
--    （sandbox_docker_prebuild_done 镜像预构建标记），以精简迁移脚本数量。
-- 2. 策略：local(默认) / docker / e2b / ssh；各策略可配参数见下方说明。
-- 3. INSERT IGNORE：key 已存在时忽略整行，不覆盖已有部署的 value，避免升级时丢失用户环境配置。
-- 4. sandbox_docker_prebuild_done：记录 docker 选项使用的镜像是否已完成一次预构建（值 'true'），
--    用于前端展示预构建状态与加速后续容器启动；由系统在预构建接口执行时写入。
INSERT IGNORE INTO system_configs (`key`, `value`, `description`, `category`, `is_secret`, `created_at`, `updated_at`)
VALUES
('sandbox_policy', 'local', '智能体沙箱执行策略：local=宿主机本地工作区（默认）；docker=Docker 工作区（自动构建并运行容器，容器内提供 Bash/文件工具）；e2b=E2B 云端沙箱。', 'sandbox', 0, NOW(6), NOW(6)),
('sandbox_docker_base_image', '', 'Docker 沙箱使用的基础镜像（默认采用框架内置镜像）；支持配置阿里 ACR 等其他镜像源，留空则用官方默认。', 'sandbox', 0, NOW(6), NOW(6)),
('sandbox_docker_host_workdir', '', 'Docker 沙箱挂载到容器的宿主机工作目录；留空=纯临时容器，每次会话用完即销毁（推荐）；填写=进阶跨会话/跨容器持久共享。', 'sandbox', 0, NOW(6), NOW(6)),
('sandbox_e2b_api_key', '', 'E2B 云端沙箱的 API Key；留空时回退读取环境变量 E2B_API_KEY。', 'sandbox', 1, NOW(6), NOW(6)),
('sandbox_e2b_template', '', 'E2B 沙箱使用的模板标识；留空使用默认 Sandbox 模板。', 'sandbox', 0, NOW(6), NOW(6)),
('sandbox_e2b_timeout_seconds', '300', 'E2B 沙箱会话超时时间（秒），默认 300。', 'sandbox', 0, NOW(6), NOW(6)),
('sandbox_ssh_host', '', 'SSH 沙箱（ssh 策略）远程主机地址：IP 或域名；配合端口/用户登录远程沙箱主机。', 'sandbox', 0, NOW(6), NOW(6)),
('sandbox_ssh_port', '22', 'SSH 沙箱连接端口，默认 22。', 'sandbox', 0, NOW(6), NOW(6)),
('sandbox_ssh_user', '', 'SSH 沙箱登录用户名。', 'sandbox', 0, NOW(6), NOW(6)),
('sandbox_ssh_auth_type', 'password', 'SSH 沙箱认证方式：password=密码认证（需 sshpass）；private_key=私钥认证（推荐，无需额外依赖）。', 'sandbox', 0, NOW(6), NOW(6)),
('sandbox_ssh_password', '', 'SSH 沙箱登录密码（当 auth_type=password 时使用）。', 'sandbox', 1, NOW(6), NOW(6)),
('sandbox_ssh_private_key', '', 'SSH 沙箱私钥内容（当 auth_type=private_key 时使用）；将密钥内容暂存到临时文件中用于 ssh -i 登录。', 'sandbox', 1, NOW(6), NOW(6)),
('sandbox_ssh_remote_workdir', '/workspace', 'SSH 沙箱远程工作目录，默认 /workspace。', 'sandbox', 0, NOW(6), NOW(6)),
('sandbox_docker_prebuild_done', '', 'Docker 沙箱镜像是否已完成预构建（内部标记：''true'' 表示已预构建），由系统在预构建接口执行后写入。', 'sandbox', 0, NOW(6), NOW(6));