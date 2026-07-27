# PostgreSQL 数据库初始化

`db-prod-pg` 是平台主库 PostgreSQL 的独立初始化入口。它与现有的
`db-prod/` MySQL 历史迁移链并行维护：MySQL 目录不改写，PG 新环境从
`V0-baseline.sql` 当前状态基线开始。

## 初始化

推荐在项目根目录执行：

```bash
./db-prod-pg/apply-sql.sh
```

脚本会自动扫描 `db-prod-pg/V*.sql`，按版本号自然顺序（V0、V1、V2……）执行，
然后依次确认 PostgreSQL Host、Port、User、Password 和目标数据库。目标库不存在时
会自动创建目标库，每个版本文件在独立事务中执行。目标库必须显式输入，且不会允许
使用 `postgres`、`template0` 或 `template1` 作为业务目标库。

重复执行 `./db-prod-pg/apply-sql.sh` 是安全的，但后续新增的每个 `V*.sql` 必须自行
使用 `IF NOT EXISTS`、`ON CONFLICT` 等 PostgreSQL 幂等写法。也可以显式传入一个或
多个版本文件，只执行传入的文件：

```bash
./db-prod-pg/apply-sql.sh db-prod-pg/V1-add-feature.sql
./db-prod-pg/apply-sql.sh db-prod-pg/V1-add-feature.sql db-prod-pg/V2-add-index.sql
```

使用 `./db-prod-pg/apply-sql.sh` 导入 `V0-baseline.sql` 成功后，脚本会询问是否
创建默认 `admin` 用户。选择 `Y` 后会使用当前 `ENCRYPTION_KEY` 生成新的 API Key，
不会把固定 API Key 或密码写入 PostgreSQL 基线。

也可以直接调用导入器：

```bash
python3 db-prod-pg/apply_sql.py db-prod-pg/V0-baseline.sql \
  --host 127.0.0.1 \
  --port 5432 \
  --user postgres \
  --password '<password>' \
  --database nanzi_ai_agent_platform
```

需要 PostgreSQL 14+ 和项目依赖中的 `psycopg`（已存在于 `requirements.txt`；本次已用 PostgreSQL 16.14 实测）。生产环境执行前，
请先备份数据库，并确认当前用户拥有创建数据库、建表和建索引的权限。

## 启用平台运行时

初始化完成后，平台主库通过环境变量选择数据库类型。默认仍是 MySQL：

```dotenv
DATABASE_TYPE=mysql
```

切换到 PostgreSQL 时，配置 PostgreSQL 连接参数：

```dotenv
DATABASE_TYPE=postgresql
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=nanzi_ai_agent_platform
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<password>
```

应用 ORM 和 APScheduler 会分别使用 `postgresql+psycopg` 异步/同步连接；
不配置 `DATABASE_TYPE` 时保持原有 MySQL 行为。

## 管理员初始化与凭证维护

两个数据库目录都只提供便捷包装入口，实际逻辑共用项目根目录的脚本，并根据
`DATABASE_TYPE` 连接当前平台主库：

```bash
# 创建 admin（已存在且为管理员时幂等跳过）
./db-prod-pg/create-admin-user.sh

# 创建或重新生成 admin API Key；明文只在终端显示一次
./db-prod-pg/create-admin-key.sh

# 交互输入两次新密码，不会把密码放在命令行参数中
./db-prod-pg/reset-admin-password.sh
```

如果使用自定义用户名，可将用户名作为第一个参数传给三个脚本。管理员脚本要求目标
用户已经是 `admin` 角色，不会把普通用户静默提升为管理员。

## 版本约定

- `V0-baseline.sql` 是新 PostgreSQL 环境的当前状态基线，不是 MySQL 的逐文件翻译。
- 每个字段的中文说明直接放在对应 `CREATE TABLE` 的字段定义上方；由于 PostgreSQL 不支持字段行内的 MySQL `COMMENT` 语法，脚本同时用 `COMMENT ON COLUMN` 将说明写入数据库元数据。
- 后续 PostgreSQL 变更新增到本目录，沿用 `V1-...sql`、`V2-...sql` 的编号，按
  PostgreSQL 方言编写，并由同一个 `apply_sql.py` 导入。
- `db-prod/` 继续保留 MySQL 的历史版本和升级路径；不要把 PG 语句回写到其中。
- 本基线不包含任何真实 API Key、密码或外部数据库凭据；部署环境通过配置注入。
- MySQL 专用的审计日志分区维护不直接复制到基线。PG 运行时会跳过分区扩容，
  并使用普通表的微批量清理；如需原生 PostgreSQL 分区，应新增独立的分区/归档设计。
- 平台运行时的配置、ORM、同步调度器、核心 upsert、配置查询和常用运维脚本均已按
  `DATABASE_TYPE` 选择数据库；仍依赖 MySQL 历史 DDL 的重建脚本会在 PostgreSQL 下拒绝执行。
