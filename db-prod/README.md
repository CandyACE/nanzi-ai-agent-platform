# 数据库初始化与升级指南

本目录包含南孜 AI Agent 平台生产环境的数据库初始化脚本 (Migrations) 以及部署脚本。
在运行初始化或迁移时，如果目标数据库不存在，导入脚本（无论是 Python 版还是纯 Shell 版）均会自动以 `utf8mb4` 字符集创建该数据库，无须您提前建库。

## 📁 文件结构

| 文件名/目录 | 用途 |
| :--- | :--- |
| `V0` - `V*.sql` | 版本化的数据库迁移脚本（按序号从小到大执行），涵盖建表、配置初始化等。 |
| `INIT-USER-ADMIN.sql` | 默认管理员账号初始化脚本（含预置的 API Key）。 |
| `apply-sql.sh` | 基于 Python (aiomysql) 的交互式数据库部署脚本。 |
| `apply-sql-native.sh` | 免 Python 依赖的原生 Shell 交互式导入脚本（仅依赖 `mysql` CLI 客户端）。 |
| `apply_sql.py` | 实际执行 SQL 导入的核心 Python 脚本（由 `apply-sql.sh` 调用）。 |
| `create-admin-user.sh` | 使用当前 `.env` 创建默认管理员账号的入口。 |
| `create-admin-key.sh` | 创建或重新生成管理员 API Key 的入口。 |
| `reset-admin-password.sh` | 交互式重置管理员登录密码的入口。 |

---

## 🚀 数据库部署步骤

### 第一步：手动创建数据库（可选）

如果目标数据库不存在，部署脚本在运行时会自动以 `utf8mb4` 字符集创建它。但如果您需要自定义库名或有特殊的初始化字符集要求，可登录您的 MySQL 服务提前手动创建一个干净的数据库：

```sql
CREATE DATABASE IF NOT EXISTS `nanzi_ai_agent_platform` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
```

### 第二步：运行结构初始化脚本

平台提供了引导式脚本来自动扫描并顺序执行所有 `V*.sql`。您可以根据环境选择以下两种运行途径之一：

#### 💡 选项 A：使用 Python 虚拟环境导入（推荐）
需要在本地准备好 Python3 虚拟环境并安装 `aiomysql` 依赖：
1. 确保在项目根目录下并激活了虚拟环境：
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. 运行引导脚本（提示权限不足可先执行 `chmod +x db-prod/apply-sql.sh`）：
   ```bash
   ./db-prod/apply-sql.sh
   ```

#### 💡 选项 B：免 Python 依赖的纯 Shell 脚本导入
若您部署的服务器宿主机不想配置 Python 环境，仅需保证系统已安装有 `mysql` 命令行客户端：
1. 运行免 Python 的原生脚本（提示权限不足可先执行 `chmod +x db-prod/apply-sql-native.sh`）：
   ```bash
   ./db-prod/apply-sql-native.sh
   ```

无论采用何种选项，脚本均会以交互式方式提示您依次输入数据库的 Host、Port、User、Password 及数据库名，核对配置信息并输入 **`YES`** 二次确认后即可安全导入。

> 💡 **幂等性说明**：脚本具备幂等性（Idempotency），如果某些表、字段或索引已经存在，脚本会自动跳过。重复执行时日志里可能出现 `幂等跳过（可忽略…）` 并附带 MySQL 的 `ERROR 1050/1060/1061…` 字样——这只是被吞掉的“已存在”提示，**不是失败**。只有出现 `❌ 执行失败（非幂等可忽略错误，需处理）` 才需要排查。

---

### 第三步：配置默认管理员账号（可选）

如果您是首次部署，需要配置默认的 `admin` 账号和预置 API Key 凭证。
**提示**：在执行第二步结构初始化时，导入脚本在结束时会**自动交互询问并一键导入此数据**。如果您在当时选择了跳过，或者需要重新导入，也可以通过以下指令随时进行**手动单独导入**：

* **使用 Python 工具导入**：
  ```bash
  ./db-prod/apply-sql.sh db-prod/INIT-USER-ADMIN.sql
  ```
* **使用纯 Shell 原生工具导入**：
  ```bash
  ./db-prod/apply-sql-native.sh db-prod/INIT-USER-ADMIN.sql
  ```
（同样需要输入对应的 MySQL 连接参数，并输入 `YES` 确认执行）

**💡 默认管理员账号信息说明**：
- **默认用户名**：`admin`
- **默认 API Key**：`5BYfsKWhU_Cfx83cuo8E0kd4AtEhlUHDVlKwwR2kN-c`
- **初始登录说明**：该脚本未设置初始密码。默认情况下，系统在第一次生成后**仅支持通过 API Key 进行登录和接口调用**。用户成功登录系统后，可前往用户管理或个人中心页面**自行修改并设置初始登录密码**。

---

## ⚠️ 常见问题

### Q1: 运行脚本时报错 `ModuleNotFoundError: No module named 'aiomysql'`
**原因**：在使用 `./db-prod/apply-sql.sh` 时，未在 Python 虚拟环境中安装所需的依赖。
**解决**：您可以按提示执行 `pip install -r requirements.txt` 安装相关依赖；或者，如果您不想配置 Python，可直接运行免 Python 依赖的 `./db-prod/apply-sql-native.sh` 原生脚本进行导入。

### Q2: 提示 `幂等跳过（可忽略…）` / 旧版 `Skipping (already applied)`，里面还有 `ERROR 1061` 等字样
**原因**：迁移脚本具有幂等性设计。表/字段/索引已存在时，MySQL 会返回对应错误码，脚本识别后主动跳过，避免覆盖已有结构。日志里的 `ERROR …` 是 MySQL 原始提示被引用展示，**不代表本次导入失败**。
**处理**：无需处理。只有日志出现 `❌ 执行失败（非幂等可忽略错误，需处理）` 时才需要排查。

### Q3: 如何自定义创建新的管理员？
如果不希望使用默认的 `INIT-USER-ADMIN.sql`（或已修改 `ENCRYPTION_KEY`），可在配置好 `.env` 后通过命令行按**当前密钥**生成：
```bash
./db-prod/create-admin-user.sh
# 或指定用户名：./db-prod/create-admin-key.sh <username>
```
`create-admin-user.sh` 对已存在的管理员会幂等跳过；需要重新生成 Key 时直接运行
`create-admin-key.sh`，不需要手动删除用户。终端会打印仅此一次的 API Key，请立即保存。

### Q4: 如何重置管理员登录密码？

```bash
./db-prod/reset-admin-password.sh
# 或指定用户名
./db-prod/reset-admin-password.sh admin
```

脚本会安全地交互询问两次密码，不会把密码写入命令行或日志。

---
⚠️ **安全提示**：在任何生产环境执行数据库结构变更前，请务必提前备份您的数据！
