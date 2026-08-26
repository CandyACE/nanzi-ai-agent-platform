# NanZi AI Agent Platform：Kubernetes 部署

本目录提供基于普通 Kubernetes YAML 和 Kustomize 的部署基线，不包含 Helm Chart。
默认目标是：使用现有 Docker 镜像、集群外部 MySQL/PostgreSQL 和 Redis Stack，运行一
个完整功能的单副本应用 Pod。

## 目录边界

这是 **NanZi 平台应用层** 的 K8S 部署目录，只负责把 NanZi 应用镜像运行起来并接入
已有基础设施，不负责安装或管理下面的外部依赖：

| 外部依赖/基础设施 | 是否由本目录部署 | 部署责任 |
| --- | --- | --- |
| MySQL / PostgreSQL | 否 | 用户或运维方准备数据库、账号、库表和备份策略 |
| Redis Stack / RediSearch | 否 | 用户或运维方准备 Redis、认证、高可用和持久化策略 |
| RAGFlow | 否 | 用户或运维方准备 RAGFlow 服务及其 API 凭据 |
| LLM 网关/模型服务 | 否 | 用户或运维方准备模型服务及 API Key |
| SSO、Jira 等第三方系统 | 否 | 用户或运维方准备第三方地址、账号和凭据 |
| Oracle Instant Client | 否 | 需要 Thick 模式时由用户制作对应镜像并单独挂载 |
| Ingress Controller、TLS、StorageClass | 否 | 由目标 K8S 集群或平台运维统一提供 |
| 数据库迁移 | 否 | 按 `db-prod/` 或 `db-prod-pg/` 的方案由运维方执行一次 |

本目录只提供这些外部依赖的配置接入位置和检查说明，不会创建 MySQL、PostgreSQL、Redis
或 RAGFlow 的 StatefulSet/Deployment，也不会替用户生成真实凭据。

## 给第一次部署的人：先按这 8 步做

如果你不熟悉 Kubernetes，可以只按本节操作；后面的章节用于解释细节和排查问题。

### 第 0 步：确认你手里有什么

部署需要同时具备下面几类东西：

| 需要的东西 | 用途 | 谁负责准备 |
| --- | --- | --- |
| K8S 集群和 `kubectl` | 创建 Pod、Service、PVC 等资源 | 用户/运维方 |
| NanZi Docker 镜像 | K8S 真正运行的应用 | 用户构建，或从项目制品下载 |
| MySQL 或 PostgreSQL | 保存平台用户、配置和业务数据 | 用户/运维方 |
| Redis Stack/RediSearch | 缓存、会话状态、分布式锁和向量索引 | 用户/运维方 |
| 可用 StorageClass | 为 `/app/data` 创建 PVC | K8S 集群管理员 |
| 域名和 TLS 证书 | 让浏览器通过 HTTPS 访问，可选 | 用户/运维方 |
| RAGFlow、LLM、SSO 等服务 | 按需启用的外部能力 | 用户/运维方 |

### 第 1 步：确认 `kubectl` 连的是目标集群

在部署机器上执行：

```bash
kubectl config current-context
kubectl get nodes
```

确认显示的是目标集群和目标节点。不要在不确定上下文时执行 `kubectl apply`，否则可能
把应用部署到另一个集群。

### 第 2 步：准备 NanZi 镜像

K8S 不会自动从 GitHub 源码生成镜像，必须先准备好镜像。推荐使用镜像仓库；单节点测试
也可以下载 `.tar` 后导入。

| 场景 | 做法 | 适用范围 |
| --- | --- | --- |
| 有镜像仓库 | 构建镜像、推送仓库，再在 `kustomization.yaml` 填仓库地址 | 远程集群、多节点、生产环境，推荐 |
| Docker Desktop 单节点 | 下载/构建 `.tar`，执行 `docker load`，使用本地镜像名 | 本机测试或单节点环境 |
| 多节点但没有镜像仓库 | 每个可能调度 Pod 的节点都导入同一个镜像 | 可行但维护麻烦，不推荐 |

项目已经提供官方 Release 镜像包，可以先打开
[NanZi 1.0.x Release](https://github.com/RandyChen1985/nanzi-ai-agent-platform/releases/tag/1.0.x)，
在页面的 **Assets** 中下载与 K8S 节点架构匹配的镜像归档文件。

先查看集群节点架构：

```bash
kubectl get nodes \
  -o custom-columns=NAME:.metadata.name,ARCH:.status.nodeInfo.architecture
```

| 节点架构 | Release 中应下载的资产 | 说明 |
| --- | --- | --- |
| `amd64` / `x86_64` | 文件名包含 `linux-amd64` | 常见云服务器、Intel/AMD 服务器 |
| `arm64` / `aarch64` | 文件名包含 `linux-arm64` | ARM 云服务器、鲲鹏、Ampere 等 |

下载后，在能访问目标单节点 K8S 运行时的机器上导入。文件名以 Release 页面实际显示
的版本为准：

```bash
docker load -i /path/to/下载的/nanzi-ai-agent_linux-amd64_版本.tar
docker image ls nanzi-ai-agent
```

`docker load` 输出中的 `Loaded image: nanzi-ai-agent:<版本>` 就是镜像标签。把这个
`<版本>` 填入 `kustomization.yaml`：

```yaml
images:
  - name: nanzi-ai-agent
    newName: nanzi-ai-agent
    newTag: "<版本>"
```

如果从项目源码构建，项目也提供按服务器架构构建并导出镜像的脚本：

```bash
cd /path/to/nanzi-ai-agent-platform

# x86_64 K8S 节点
./docker/build_linux_x86.sh 1.2.0

# ARM64 K8S 节点
# ./docker/build_linux_arm.sh 1.2.0
```

构建脚本会在 `docker/release/` 生成带架构和版本号的 `.tar` 文件。单节点测试可导入：

```bash
docker load -i docker/release/nanzi-ai-agent_1.2.0_linux-amd64_*.tar
docker image ls nanzi-ai-agent
```

如果是远程或多节点集群，即使镜像包是从 GitHub Release 下载的，也不能只在本机执行
`docker load`。应将镜像导入实际节点，或者更推荐先在本机导入，再重新打标签并推送到
目标集群可访问的镜像仓库：

```bash
docker tag nanzi-ai-agent:1.2.0 registry.example.com/nanzi-ai-agent:1.2.0
docker push registry.example.com/nanzi-ai-agent:1.2.0
```

如果 GitHub Release 页面只提供源码而没有镜像归档，就按上面的构建方式生成镜像。导入
镜像后仍要确认镜像架构与 K8S 节点一致；架构不一致通常会在 Pod 事件中表现为启动失败。

### 第 3 步：修改哪些文件

第一次部署通常只需要修改 `configmap.yaml`、复制并修改 `secret.example.yaml`，以及
根据镜像来源修改 `kustomization.yaml`。其他文件先不要改。

| 文件 | 第一次是否要改 | 作用 | 小白怎么处理 |
| --- | --- | --- | --- |
| `kustomization.yaml` | 是 | 指定要部署的资源，并覆盖镜像名称/标签 | 把 `newName`、`newTag` 改成实际镜像；本地镜像保持 `nanzi-ai-agent` |
| `configmap.yaml` | 是 | 保存非敏感配置，如域名、数据库地址、Redis 地址 | 按下方配置表修改 `*.example.internal` 和域名 |
| `secret.example.yaml` | 复制后改 | 提供密码和加密密钥 | 复制为 `secret.yaml`，填写真实值；不要直接提交 |
| `pvc.yaml` | 通常不用 | 为 `/app/data` 申请持久化磁盘 | 默认 20Gi、RWO；空间不够时只改容量 |
| `deployment.yaml` | 通常不用 | 创建 NanZi 应用 Pod、探针和数据卷挂载 | 先保持单副本；资源不足时再调整 CPU/内存 |
| `service.yaml` | 不用 | 让集群内部通过 80 访问应用 8001 | 保持不变 |
| `ingress.example.yaml` | 需要域名访问时 | 配置外部域名、TLS、SSE 超时和会话粘性 | 复制为 `ingress.yaml`，改域名和证书后单独应用 |
| `namespace.yaml` | 通常不用 | 创建独立的 `nanzi-ai-agent` 命名空间 | 保持不变 |

### 第 4 步：填写 `configmap.yaml`

下面是第一次部署最需要理解的配置。示例中的 `example.internal` 和
`nanzi.example.com` 都是占位值，不能直接当作真实地址使用。

| 配置项 | 示例值 | 是否必改 | 是干什么的 |
| --- | --- | --- | --- |
| `APP_PUBLIC_URL` | `https://nanzi.example.com` | 是 | 用户访问平台的公开地址，生成链接和部分通知会使用 |
| `ALLOWED_ORIGINS` | `["https://nanzi.example.com"]` | 是 | 浏览器 CORS 白名单，必须是 JSON 数组字符串 |
| `BROWSER_VIEWER_ALLOWED_ORIGINS` | `https://nanzi.example.com` | 是 | 浏览器人工接管/查看功能允许的来源 |
| `DATABASE_TYPE` | `mysql` | 是 | 主库类型，只能按实际使用 `mysql` 或 `postgresql` |
| `MYSQL_HOST` | `mysql.example.internal` | MySQL 时必改 | MySQL 服务地址；不能填 Pod 内不存在的 `localhost` |
| `MYSQL_PORT` | `3306` | MySQL 时按需 | MySQL 服务端口 |
| `MYSQL_DB` | `nanzi_ai_agent_platform` | MySQL 时按需 | MySQL 数据库名 |
| `POSTGRES_HOST` | `postgres.example.internal` | PostgreSQL 时必改 | PostgreSQL 服务地址 |
| `POSTGRES_PORT` | `5432` | PostgreSQL 时按需 | PostgreSQL 服务端口 |
| `POSTGRES_DB` | `nanzi_ai_agent_platform` | PostgreSQL 时按需 | PostgreSQL 数据库名 |
| `REDIS_HOST` | `redis.example.internal` | 是 | Redis Stack 服务地址 |
| `REDIS_PORT` | `6379` | 按需 | Redis 服务端口 |
| `REDIS_DB` | `0` | 建议保持 0 | 平台 RediSearch/向量索引使用的 Redis DB |
| `REDIS_ENABLE` | `true` | 是 | 是否启用 Redis；平台生产运行通常应保持 `true` |
| `USE_ORACLE_THICK_MODE` | `0` | 默认不用改 | 是否启用 Oracle Thick 模式；启用时还需要专用镜像和客户端挂载 |
| `TZ` / `PLATFORM_TIMEZONE` | `Asia/Shanghai` | 按部署地 | 系统和平台业务时区 |

只使用 MySQL 时，`POSTGRES_*` 可以保留占位值；只使用 PostgreSQL 时，`MYSQL_*` 可以
保留占位值，应用会根据 `DATABASE_TYPE` 选择对应的一套连接配置。

### 第 5 步：创建 `secret.yaml`

在项目根目录执行：

```bash
cp k8s_deploy/secret.example.yaml k8s_deploy/secret.yaml
```

然后编辑 `k8s_deploy/secret.yaml`。每个字段的作用如下：

| Secret 字段 | 是否必填 | 是干什么的 |
| --- | --- | --- |
| `MYSQL_USER` / `MYSQL_PASSWORD` | 使用 MySQL 时必填 | MySQL 登录账号和密码 |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | 使用 PostgreSQL 时必填 | PostgreSQL 登录账号和密码 |
| `REDIS_PASSWORD` | Redis 开启认证时必填 | Redis 登录密码；无密码时填写空字符串 |
| `ENCRYPTION_KEY` | 必填 | 加密平台保存的模型/API 凭据；必须沿用原系统值，不能随意更换 |

`secret.yaml` 不会被 `kustomization.yaml` 默认引用，也已被 `.gitignore` 排除。需要先
单独应用它。不要把真实密码写入 `configmap.yaml`、README 或 Git 提交。

### 第 6 步：先初始化数据库

数据库迁移由用户/运维方执行，不由 K8S Deployment 自动执行。只选择与
`DATABASE_TYPE` 对应的一套：

| `DATABASE_TYPE` | 使用目录 | 初始化入口 |
| --- | --- | --- |
| `mysql` | `db-prod/` | `./db-prod/apply-sql.sh` 或 `./db-prod/apply-sql-native.sh` |
| `postgresql` | `db-prod-pg/` | `./db-prod-pg/apply-sql.sh` |

例如 MySQL：

```bash
cd /path/to/nanzi-ai-agent-platform
./db-prod/apply-sql-native.sh
```

例如 PostgreSQL：

```bash
cd /path/to/nanzi-ai-agent-platform
./db-prod-pg/apply-sql.sh
```

脚本会交互询问数据库地址、端口、账号和密码。生产环境执行前先备份数据库；详细行为
和升级规则见 [MySQL 迁移说明](../db-prod/README.md) 或
[PostgreSQL 迁移说明](../db-prod-pg/README.md)。不要同时执行两套迁移。

### 第 7 步：启动 NanZi

确认镜像、数据库、Redis、PVC 和 Secret 都准备好后，在项目根目录执行：

```bash
kubectl apply -f k8s_deploy/namespace.yaml
kubectl apply -f k8s_deploy/secret.yaml
kubectl apply -k k8s_deploy
kubectl -n nanzi-ai-agent rollout status deployment/nanzi-ai-agent
```

看到 `successfully rolled out` 后，查看 Pod：

```bash
kubectl -n nanzi-ai-agent get pod,svc,pvc
kubectl -n nanzi-ai-agent logs deployment/nanzi-ai-agent --tail=200
```

### 第 8 步：访问平台

#### 没有域名时：临时本机访问

保持下面命令运行，再在浏览器打开 `http://127.0.0.1:8001`：

```bash
kubectl -n nanzi-ai-agent port-forward svc/nanzi-ai-agent 8001:80
```

健康检查可以执行：

```bash
curl http://127.0.0.1:8001/health
```

#### 有域名时：配置 Ingress

```bash
cp k8s_deploy/ingress.example.yaml k8s_deploy/ingress.yaml
```

编辑 `ingress.yaml` 中的域名和 TLS Secret，确认集群已安装 ingress-nginx 后执行：

```bash
kubectl apply -f k8s_deploy/ingress.yaml
kubectl -n nanzi-ai-agent get ingress
```

之后通过 `https://你的域名` 访问。Ingress 示例不是默认资源，不执行这一步也不影响
集群内的 Service 和 `port-forward` 访问。

## 启动后常用操作

| 目的 | 命令 | 说明 |
| --- | --- | --- |
| 查看应用状态 | `kubectl -n nanzi-ai-agent get pod` | `Running` 且 `READY` 为 `1/1` 才是基础正常 |
| 查看启动日志 | `kubectl -n nanzi-ai-agent logs deployment/nanzi-ai-agent` | 优先看数据库、Redis 和必填配置错误 |
| 查看详细事件 | `kubectl -n nanzi-ai-agent describe pod <pod名>` | 排查镜像拉取、PVC、探针失败 |
| 临时停止应用 | `kubectl -n nanzi-ai-agent scale deployment/nanzi-ai-agent --replicas=0` | 不删除 PVC，数据保留 |
| 恢复应用 | `kubectl -n nanzi-ai-agent scale deployment/nanzi-ai-agent --replicas=1` | 当前建议保持单副本 |
| 修改环境变量后生效 | `kubectl -n nanzi-ai-agent rollout restart deployment/nanzi-ai-agent` | ConfigMap/Secret 变化不会自动注入已有进程 |
| 查看历史版本 | `kubectl -n nanzi-ai-agent rollout history deployment/nanzi-ai-agent` | 用于确认升级记录 |
| 回滚应用 | `kubectl -n nanzi-ai-agent rollout undo deployment/nanzi-ai-agent` | 不会回滚 PVC 中的数据 |

不要执行 `kubectl delete pvc nanzi-ai-agent-data` 作为普通排障操作；删除 PVC 可能导致
上传文件、用户工作区和生成文件丢失。

## 当前支持结论

- **单副本 K8S 部署：支持作为基础方案验证。** 镜像监听 8001，应用配置通过环境变量
  注入，`/app/data` 通过 PVC 保存。
- **多副本基础设施：可以继续建设，但当前不能直接视为完整高可用。** 浏览器运行时、
  SSE/人工接管事件和部分执行状态仍有进程内注册表；调度器虽然使用数据库 JobStore
  和部分 Redis 锁，但当前启动方式不是完整的单 Leader 调度。
- **默认不启用 Docker Socket。** 现有 Docker Compose 使用 DooD 方式让应用控制宿主机
  Docker；K8S 中直接挂载 `/var/run/docker.sock` 会扩大 Pod 权限边界，必须针对执行隔离、
  宿主机路径映射和安全策略单独设计。

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `kustomization.yaml` | 默认资源入口，不包含真实 Secret 和 Ingress 示例 |
| `namespace.yaml` | 创建 `nanzi-ai-agent` 命名空间 |
| `configmap.yaml` | 非敏感配置和外部数据库/Redis 地址，占位地址需修改 |
| `secret.example.yaml` | Secret 模板，不要直接应用或提交真实值 |
| `pvc.yaml` | `/app/data` 的 20Gi、`ReadWriteOnce` PVC |
| `deployment.yaml` | 单副本 Deployment、环境变量、PVC 和 `/health` 探针 |
| `service.yaml` | ClusterIP Service，端口 80 转发到容器 8001 |
| `ingress.example.yaml` | ingress-nginx 的可选示例，含 SSE 超时和会话粘性 |

## 常见问题与注意事项

排查时建议按“Pod 状态 → 应用日志 → 数据库/Redis → PVC → Ingress”的顺序进行，不要一
开始就删除 Pod、PVC 或重新初始化数据库。

| 现象 | 常见原因 | 检查与处理 |
| --- | --- | --- |
| `CreateContainerConfigError` | Secret 不存在、名称不一致或命名空间错误 | 确认先创建 `nanzi-ai-agent-secret`，并检查 `kubectl -n nanzi-ai-agent describe pod ...` |
| `ImagePullBackOff` | 镜像地址/标签错误、私有仓库未认证、节点无法访问仓库 | 检查 `image`、`imagePullSecrets` 和 Pod 事件；使用 `docker load` 时确认镜像已导入实际调度节点及其容器运行时 |
| `Pending` 或 PVC 挂载失败 | 集群没有默认 StorageClass、容量不足或 RWO 卷仍被旧 Pod 占用 | 检查 `kubectl -n nanzi-ai-agent describe pvc nanzi-ai-agent-data`；不要为了排障删除 PVC |
| Pod 正常但公共文档/上传文件消失 | PVC 挂载 `/app/data` 后遮住了镜像内同路径内容，或 PVC 没有初始化 | 按“初始化 `/app/data`”章节把必要的 `data/` 内容同步到 PVC |
| `CrashLoopBackOff` | 应用启动阶段连接数据库/Redis失败、必填环境变量缺失或镜像启动异常 | 先看 `kubectl -n nanzi-ai-agent logs deployment/nanzi-ai-agent --previous`，再核对 ConfigMap、Secret、DNS、端口和网络策略 |
| 数据库连接失败或表不存在 | 地址、端口、账号、数据库类型错误，或迁移没有完成 | 确认 `DATABASE_TYPE` 与实际数据库一致；MySQL 和 PostgreSQL 迁移分别执行一次，不要混用 |
| Redis 连接成功但向量/知识库功能异常 | Redis 不是 Redis Stack/RediSearch、密码错误或 `REDIS_DB` 不为 0 | 检查 Redis 版本、认证和 `REDIS_DB=0`；所有副本必须连接同一个 Redis |
| Ingress 返回 404/502/504 | Ingress Class、域名、TLS、Service 端口或后端 Pod 不匹配 | 先绕过 Ingress 用 `port-forward` 验证 Service，再检查 Ingress 事件和 Controller 日志 |
| SSE 中途断开、浏览器人工接管异常 | 代理缓冲/超时、会话粘性未配置或连接经过多个代理 | 使用示例中的超时和关闭缓冲设置；非 NGINX Controller 按其语法配置，并验证长连接 |
| 修改 ConfigMap/Secret 后应用仍使用旧值 | 环境变量只在进程启动时读取 | 修改后执行 `kubectl -n nanzi-ai-agent rollout restart deployment/nanzi-ai-agent`，再检查新 Pod 日志 |
| Docker 沙箱、代码执行或部分工具不可用 | 默认清单没有挂载 Docker Socket，避免把宿主机 Docker 控制权暴露给 Pod | 这是默认安全边界，不要直接照搬 Compose 的 Socket 挂载；需要该能力时单独设计隔离执行器 |
| 多副本后任务重复、会话丢失或取消不生效 | 调度器和部分浏览器/执行状态仍然是进程级状态 | 不要只修改 `replicas`；先完成共享存储、会话路由、Scheduler Leader 和跨 Pod 运行态验证 |
| Pod 被 OOMKilled 或请求超时 | Playwright、Agent 执行和并发模型调用需要更多 CPU/内存 | 查看 `kubectl describe pod` 的退出原因，根据压测调整 requests/limits 和并发策略 |

### 上线前最小检查清单

- [ ] 镜像使用明确版本标签，且目标节点或镜像仓库可拉取该版本。
- [ ] `DATABASE_TYPE`、数据库地址、账号和迁移版本匹配。
- [ ] Redis 为共享的 Redis Stack/RediSearch，`REDIS_DB=0`，网络和认证可用。
- [ ] `ENCRYPTION_KEY` 沿用原系统值，未写入 ConfigMap 或代码仓库。
- [ ] PVC 已绑定，`/app/data` 中的公共文档、上传目录和用户数据已确认。
- [ ] `APP_PUBLIC_URL`、CORS 域名和 Ingress/TLS 域名一致。
- [ ] 已用 `/health`、登录、文件读写、模型调用和 SSE 分别验证，而不是只看 Pod 为 `Ready`。
- [ ] 当前仍保持单副本；若要扩容，已完成“多副本前置条件”中的专项验证。
- [ ] 已确认是否需要 Docker 沙箱；需要时已经过独立安全评审，不直接挂载宿主机 Socket。

## 升级和回滚

修改镜像标签或配置后重新应用资源，并等待滚动状态：

```bash
kubectl apply -k k8s_deploy
kubectl -n nanzi-ai-agent rollout status deployment/nanzi-ai-agent
```

当前 Deployment 使用单副本 + `Recreate`，升级期间会有短暂不可用窗口，但可以避免
`ReadWriteOnce` PVC 被新旧 Pod 同时挂载。需要回滚时：

```bash
kubectl -n nanzi-ai-agent rollout undo deployment/nanzi-ai-agent
kubectl -n nanzi-ai-agent rollout status deployment/nanzi-ai-agent
```

PVC 不随 Deployment 回滚，回滚前应确认新版本没有改变数据格式；删除 PVC 会造成用户文件、
上传内容和工作区数据丢失，禁止把删除 PVC 当作常规排障步骤。

## 多副本前置条件

只有满足下表条件后，才应把 `deployment.yaml` 的 `replicas` 改大：

| 项目 | 当前情况 | 多副本要求 |
| --- | --- | --- |
| 数据库 | 外部共享数据库 | 所有 Pod 使用同一主库/读写拓扑 |
| Redis | 外部 Redis，保存缓存、状态和分布式锁 | 所有 Pod 使用同一可用 Redis；按需建设 Sentinel/Cluster |
| 文件 | 默认单 PVC、RWO | 改为可靠的 RWX 共享存储或对象存储，并验证并发读写 |
| 浏览器 | Worker 和事件订阅包含进程内注册表 | Ingress 会话粘性只能缓解，仍需验证断线/重连/人工接管 |
| 会话运行 | 部分活动运行和取消状态进程内 | 需验证跨 Pod 请求、取消和 SSE 连接行为 |
| 调度器 | 每个应用进程启动调度器；仅部分任务使用 Redis 锁 | 需要单 Leader/独立 Scheduler 或完整分布式去重机制 |
| Docker 沙箱 | Docker Compose 依赖宿主机 Socket | K8S 中需单独设计安全执行器，不能直接照搬 Socket 挂载 |

因此，当前文档只把单副本作为完整功能基线；多副本属于后续架构改造和验收事项，不是
修改一个 `replicas` 数字即可完成的部署动作。

## 本地静态验证

在提交资源前可执行：

```bash
kubectl kustomize k8s_deploy
kubectl apply --dry-run=client -k k8s_deploy
```

如果本机没有 `kubectl`，至少使用 YAML 解析器检查语法，并人工确认：默认资源不含真实
Secret、Ingress 示例未被默认引用、没有 Helm 模板、没有 Docker Socket、没有数据库迁移 Job。

本目录不代表已经完成真实集群验收；镜像拉取、PVC 绑定、数据库/Redis 连通性、Ingress
TLS、浏览器运行时和长连接行为仍需在目标集群由部署人员验证。
