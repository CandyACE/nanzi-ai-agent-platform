# K8S 部署资源设计

## 背景

当前平台已经通过 `docker/Dockerfile` 产出单个 HTTP 应用镜像，应用监听
8001 端口，数据库和 Redis 通过环境变量连接外部服务。现需要补充一套不依赖
Helm 的 Kubernetes 基础部署资源和中文部署文档，方便在已有 K8S 集群中运行。

## 目标

- 在仓库根目录增加 `k8s_deploy/`，提供可被 `kubectl apply -k` 渲染和应用的基础资源。
- 覆盖命名空间、配置、密钥模板、持久化卷、Deployment、Service 及可选 Ingress。
- 与现有 Docker 镜像、环境变量和 `/app/data` 数据目录保持一致。
- 明确单副本默认方案与当前多副本运行时限制，避免把“容器可运行”误写成“完整高可用”。
- 不在 K8S 资源中管理 MySQL、PostgreSQL 或 Redis 等已有外部依赖。
- 明确 RAGFlow、LLM、SSO/Jira、Oracle Client、Ingress Controller、StorageClass 和数据库迁移
  也属于部署方准备的外部前置，不由本目录创建。
- 不把真实凭据、宿主机路径或 Docker Socket 写入仓库默认资源。

## 非目标

- 不创建 Helm Chart、Operator 或云厂商专用资源。
- 不修改应用代码、数据库迁移或 Docker 镜像构建流程。
- 不提供默认的 MySQL/Redis StatefulSet。
- 不提供 RAGFlow、LLM、SSO/Jira 等第三方服务的部署资源。
- 不默认把 `/var/run/docker.sock` 暴露给 Pod。
- 不在 Pod 启动时自动执行数据库迁移。

## 方案选择

### 方案 A：基础 YAML + Kustomize（采用）

用一组普通 Kubernetes YAML 配合 `kustomization.yaml` 组织资源。基础部署默认为
单副本、`Recreate` 策略和 `ReadWriteOnce` PVC，适合先验证镜像、外部数据库、Redis
和集群网络；Ingress 作为示例资源单独提供，不强制绑定具体 Ingress Controller。

优点是依赖少、可审阅、可直接使用 `kubectl`，也方便后续按环境增加 Kustomize
overlay。多副本不作为默认值，须在共享存储、会话粘性和调度器策略完成后再开启。

### 方案 B：Helm Chart

可通过 values 管理镜像、域名和资源限制，但会引入模板层和额外发布约定。当前部署
参数数量有限，先不采用。

### 方案 C：集群内同时部署数据库和 Redis

能形成单目录完整安装包，但会把有状态组件的备份、升级和高可用责任带入应用目录，
也与当前 Docker 独立生产配置连接外部依赖的方式不一致。当前不采用。

## 资源设计

| 文件 | 用途 | 是否默认应用 |
| --- | --- | --- |
| `namespace.yaml` | 创建 `nanzi-ai-agent` 命名空间 | 是 |
| `configmap.yaml` | 非敏感配置和外部依赖地址 | 是 |
| `secret.example.yaml` | 数据库、Redis、加密密钥占位模板 | 否，需复制后填写 |
| `pvc.yaml` | 持久化 `/app/data` | 是 |
| `deployment.yaml` | 单副本应用、探针和数据卷挂载 | 是 |
| `service.yaml` | 集群内 80 → Pod 8001 | 是 |
| `ingress.example.yaml` | NGINX Ingress、SSE/长请求超时和会话粘性示例 | 否，按环境修改 |
| `kustomization.yaml` | 组织默认资源和镜像覆盖点 | 是 |

默认 Deployment 不挂载 Docker Socket。当前应用的浏览器运行时、会话事件订阅、部分
执行注册表位于进程内；任务调度器虽使用数据库 JobStore 和部分 Redis 锁，但系统任务
并非完整的单 Leader 调度。因此文档将单副本标为当前完整功能基线，多副本仅列出前置
条件和已知风险。

## 配置和数据约定

- `DATABASE_TYPE=mysql` 时配置 `MYSQL_*`；使用 PostgreSQL 时改为 `postgresql` 并配置
  `POSTGRES_*`，两套数据库迁移仍须分别执行。
- `REDIS_DB` 默认使用 `0`，因为平台的 RediSearch/向量索引约束要求索引位于 DB 0。
- `ENCRYPTION_KEY` 必须在 Secret 中固定保存；更换会影响已加密的模型/API 凭据。
- `/app/data` 保存上传文件、用户工作区、生成文件、浏览器相关文件和公共文档目录，
  PVC 初始化时需要保留现有数据结构；不能把它当作临时容器层。
- `ALLOWED_ORIGINS` 使用 Pydantic 可解析的 JSON 数组字符串，并与 Ingress 对外域名一致。
- Docker 沙箱若仍需使用，必须单独评估 K8S 下的执行隔离、宿主机路径映射和安全权限，
  不通过默认资源静默启用。

## 健康检查

当前应用公开 `/health`，返回固定的 `status: ok`。Deployment 使用它作为启动、存活
和基础就绪探针，但文档会明确：它不能证明 MySQL、Redis、PVC 或后台调度器已经就绪。
后续如果新增真实依赖检查端点，应只替换 readinessProbe，不改变对外 Service 端口。

## 验证方式

提交前仅做本地静态验证：检查 YAML 语法、`kubectl kustomize k8s_deploy` 渲染结果、
`kubectl apply --dry-run=client -k k8s_deploy`（若本机安装 kubectl），并确认默认资源中
没有真实凭据、Helm 文件、Docker Socket 或数据库迁移 Job。不会连接集群或启动服务。
