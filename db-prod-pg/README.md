# PostgreSQL 数据库初始化与版本升级

`db-prod-pg` 是平台主库 PostgreSQL 的独立初始化与升级入口。它与现有的
`db-prod/` MySQL 历史迁移链并行维护：MySQL 目录不改写，PostgreSQL 新环境从
`V0-baseline.sql` 当前状态基线开始，后续升级继续使用本目录的 `V*.sql` 文件。

## 先判断应该怎么执行

| 场景 | 推荐命令 | 执行范围 |
| --- | --- | --- |
| 新 PostgreSQL 环境首次初始化 | `./db-prod-pg/apply-sql.sh` | 自动执行当前目录全部 `V*.sql`，按版本号排序 |
| 已初始化环境，重复校准全部版本 | `./db-prod-pg/apply-sql.sh` | 再次执行当前存在的全部 `V*.sql` |
| 后续只升级一个版本 | `./db-prod-pg/apply-sql.sh db-prod-pg/V3-xxx.sql` | 只执行传入的一个 SQL 文件 |
| 后续连续升级多个版本 | `./db-prod-pg/apply-sql.sh db-prod-pg/V3-xxx.sql db-prod-pg/V4-xxx.sql` | 只执行传入文件，并按命令行顺序执行 |

推荐始终从项目根目录执行显式文件命令：

```bash
cd /Users/chenxiaolong/workspace/nanzi-ai-agent-platform
./db-prod-pg/apply-sql.sh db-prod-pg/V3-add_mcp_scope_and_user_id.sql
```

如果当前已经在 `db-prod-pg` 目录，无参数执行仍然可以：

```bash
cd /Users/chenxiaolong/workspace/nanzi-ai-agent-platform/db-prod-pg
./apply-sql.sh
```

但在 `db-prod-pg` 目录下指定文件时，建议使用绝对路径，因为脚本启动后会切换到
项目根目录：

```bash
./apply-sql.sh "$PWD/V3-add_mcp_scope_and_user_id.sql" \
               "$PWD/V4-add_category_to_chatbi_examples.sql"
```

## 一、首次初始化：单次全量执行

在项目根目录执行：

```bash
./db-prod-pg/apply-sql.sh
```

不传 SQL 文件参数时，`apply-sql.sh` 会：

1. 扫描 `db-prod-pg/V*.sql`；
2. 按版本号自然排序，例如 `V0`、`V1`、`V2`、`V10`；
3. 依次询问数据库连接信息；
4. 对每个版本文件调用 `apply_sql.py`；
5. 所有文件成功后，如果本次包含 `V0-baseline.sql`，再询问是否创建默认管理员。

当前交互输入规则：

```text
PostgreSQL host [localhost]:   # 留空使用 localhost
PostgreSQL port [5432]:        # 留空使用 5432
PostgreSQL user:               # 必填
PostgreSQL password:           # 密码输入不回显
Target database:               # 必填
```

目标数据库不存在时，导入器会先连接 PostgreSQL 管理库并创建目标数据库。目标库
不能是 `postgres`、`template0` 或 `template1`。

全量执行前请确认：

- PostgreSQL 版本满足项目要求（当前基线按 PostgreSQL 14+ 编写）；
- 当前用户有创建数据库、建表、建索引和写入数据的权限；
- 目标数据库已备份，或确认这是一个可以初始化/升级的环境；
- `db-prod-pg` 中当前存在的所有 `V*.sql` 都属于本次目标环境。

## 二、后续升级：只执行单个 SQL

当环境已经完成 V0 到 V2，只新增了 V3 时，不需要再次指定全量文件，可以只执行
V3：

```bash
cd /Users/chenxiaolong/workspace/nanzi-ai-agent-platform
./db-prod-pg/apply-sql.sh \
  db-prod-pg/V3-add_mcp_scope_and_user_id.sql
```

脚本会重新确认连接目标，但只会把这个文件交给导入器。它不会因为文件名是 V3 就
自动判断数据库当前版本，也不会扫描并执行其他版本。

## 三、后续升级：一次指定多个 SQL

如果 V3、V4 尚未执行，需要连续升级多个版本，可以显式按顺序传入：

```bash
cd /Users/chenxiaolong/workspace/nanzi-ai-agent-platform
./db-prod-pg/apply-sql.sh \
  db-prod-pg/V3-add_mcp_scope_and_user_id.sql \
  db-prod-pg/V4-add_category_to_chatbi_examples.sql
```

传入多个文件时：

- 只执行命令行中列出的文件；
- 按命令行顺序执行，不会重新排序；
- 调用方应按 V3、V4、V5……的顺序传入；
- 任意文件失败后立即停止，后续文件不会执行。

因此，升级多个文件时不要依赖 shell 的通配顺序，推荐显式写出并按版本排列：

```bash
./db-prod-pg/apply-sql.sh \
  db-prod-pg/V3-add_mcp_scope_and_user_id.sql \
  db-prod-pg/V4-add_category_to_chatbi_examples.sql \
  db-prod-pg/V5-register_example_search_tool.sql
```

## 四、失败后的恢复与重新执行

每个 SQL 文件在独立事务中执行：

- V3 成功后，V3 的事务提交；随后 V4 失败，不会回滚已经提交的 V3；
- V4 内部前几条语句成功、最后一条失败时，V4 整个文件回滚；
- 失败文件之后的版本不会执行；
- 修复失败文件后，可以只重新执行失败文件及其后尚未执行的文件。

例如 V3 已经成功、V4 失败，修复 V4 后可以从项目根目录执行：

```bash
./db-prod-pg/apply-sql.sh \
  db-prod-pg/V4-add_category_to_chatbi_examples.sql \
  db-prod-pg/V5-register_example_search_tool.sql
```

也可以直接重新执行全量入口：

```bash
./db-prod-pg/apply-sql.sh
```

但全量重跑会重新执行所有当前存在的 `V*.sql`，生产环境更推荐只传入失败版本及
后续版本，减少不必要的配置更新和排查范围。

## 五、幂等执行边界

`apply-sql.sh` 不维护独立的迁移版本表，也不会记录“某个 V 文件已经执行过”。
它每次都是根据当前参数重新调用 SQL 文件，因此重复执行是否安全由每个 SQL 文件的
内容决定。

新增 PostgreSQL 迁移时应遵守：

- 建表使用 `CREATE TABLE IF NOT EXISTS`；
- 加列、索引等操作使用对应的幂等写法；
- 有真实唯一约束或主键时才使用 `ON CONFLICT`；普通索引不能用于 `ON CONFLICT`；
- 对无唯一约束的种子数据使用 `WHERE NOT EXISTS`，或先补充正确的唯一约束；
- PostgreSQL 布尔字段使用 `TRUE` / `FALSE`，不要沿用 MySQL 的 `1` / `0`；
- 重复执行不应无条件覆盖管理员或部署环境已经修改的配置，除非迁移明确就是强制校准；
- 每个版本文件都应在 PostgreSQL 方言下单独验证，并保持可重跑。

当前版本的重复执行语义也需要注意：

- V0 的表、索引和基础种子使用 PostgreSQL 幂等写法；
- V1 冲突时更新配置元数据，不覆盖已有配置值；
- V2 会把记忆 Embedding 模型和维度重新写为 `bge-m3` / `1024`，因此重跑可能覆盖
  这两个配置的人工修改；
- V3、V4、V5 的结构和种子语句按 PostgreSQL 幂等方式编写。

这意味着“幂等”表示重复执行不会重复建表、重复插入同一条种子或因已存在对象而失败，
不等于所有 SQL 都会保留人工修改过的配置值。

## 六、版本文件维护规则

- `V0-baseline.sql` 是新 PostgreSQL 环境的当前状态基线，不是 MySQL 逐文件翻译。
- 后续 PostgreSQL 变更新增到本目录，使用新的最高版本号，例如 `V6-...sql`。
- 不要把新的 PostgreSQL 迁移插入已经发布的旧版本号中。
- 如果某个版本文件尚未在任何环境执行，可以直接修正该文件。
- 如果某个版本文件已经在环境中执行，不要直接修改其历史语义；应新增下一个版本的
  修复迁移，避免不同环境无法判断实际结构。
- `db-prod/` 继续保留 MySQL 历史版本和升级路径；不要把 PostgreSQL 语句回写到其中。
- 文件名和路径不要包含空格；显式传入多个文件时按依赖顺序排列。

## 七、`apply-sql.sh` 与 `apply_sql.py` 的区别

### `apply-sql.sh`：推荐的运维入口

它负责交互和编排：

- 扫描并排序全部 `V*.sql`；
- 支持单个或多个显式 SQL 文件；
- 提供 Host、Port、User、Password、Database 输入和总确认；
- 空 Host/Port 默认使用 `localhost` / `5432`；
- 逐个调用 Python 导入器；
- 全量包含 V0 时可继续创建默认 `admin` 用户。

推荐执行：

```bash
./db-prod-pg/apply-sql.sh
```

### `apply_sql.py`：单文件实际导入器

它负责真正的 PostgreSQL 工作：

- 校验目标数据库名称；
- 必要时创建目标数据库；
- 解析 PostgreSQL 字符串、分号和 `DO $$...$$` 语句；
- 以单文件事务执行 SQL，失败时回滚当前文件。

直接调用时必须自己指定 SQL 文件和连接参数，不会自动扫描全部版本，也不会创建默认
管理员：

```bash
python3 db-prod-pg/apply_sql.py \
  db-prod-pg/V3-add_mcp_scope_and_user_id.sql \
  --host localhost \
  --port 5432 \
  --user postgres \
  --password '<password>' \
  --database nanzi_demo \
  --yes
```

不传 `--yes` 时，导入器会对单个 SQL 文件再次确认。使用 `--interactive` 可以让它
交互补齐缺少的 Host、User、Password 或 Database；自动化环境不应把密码直接写进 shell
历史，建议使用安全的环境变量或其他凭据注入方式。

## 八、启用平台运行时

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

应用 ORM 和 APScheduler 会分别使用 `postgresql+psycopg` 异步/同步连接；不配置
`DATABASE_TYPE` 时保持原有 MySQL 行为。

## 九、管理员初始化与凭证维护

使用 `apply-sql.sh` 全量导入 `V0-baseline.sql` 成功后，脚本会询问是否创建默认 `admin`
用户。选择 `Y` 后会使用当前 `ENCRYPTION_KEY` 生成新的 API Key，不会把固定 API Key
或密码写入 PostgreSQL 基线。

也可以在数据库初始化后单独维护管理员：

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

## 十、数据库和安全注意事项

- 生产环境执行前先备份目标数据库；
- 确认 Host、Port、User、Database 和本次 SQL 文件清单；
- 不要把真实密码、API Key 或外部数据库凭据提交到 SQL 文件；
- 不要把业务库目标指定为 `postgres`、`template0` 或 `template1`；
- `apply-sql.sh` 使用 Bash；脚本支持通过 `sh apply-sql.sh` 启动，并会在需要时切换到
  `bash`；
- PostgreSQL 专用 SQL 不要回写 MySQL 迁移目录；
- MySQL 专用的审计日志分区维护不直接复制到基线。PG 运行时会跳过分区扩容，并使用
  普通表的微批量清理；如需原生 PostgreSQL 分区，应新增独立的分区/归档设计。
