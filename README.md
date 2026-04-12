# SkyCLI

[![PyPI version](https://img.shields.io/pypi/v/skycli)](https://pypi.org/project/skycli/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python versions](https://img.shields.io/badge/python-3.8%2B-3776AB.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-success.svg)]()

> 🚀 **简单、强大、高效的 S3 兼容对象存储管理/迁移工具**

基于 AWS S3 SDK (boto3) 开发，支持管理和迁移 S3 协议兼容的对象存储服务（AWS S3、MinIO、Ceph、阿里云 OSS、腾讯云 COS 等）。

***

## 📖 目录

- [功能特性](#-功能特性)
- [安装指南](#-安装指南)
- [快速开始](#-快速开始)
- [命令参考](#-命令参考)
  - [配置管理](#-配置管理-config)
  - [存储桶操作](#-存储桶操作-bucket)
  - [对象操作](#-对象操作-object)
  - [元数据管理](#-元数据管理-metadata)
  - [ACL 管理](#-acl-管理-acl)
  - [数据同步](#-数据同步-sync)
  - [数据校验](#-数据校验-validate)
- [配置说明](#-配置说明)
- [常见问题](#-常见问题)
- [更新日志](#-更新日志)
- [贡献指南](#-贡献指南)

***

## ✨ 功能特性

| 特性            | 说明               |
| ------------- | ---------------- |
| 🔧 **多源配置**   | 支持多个存储源配置管理      |
| 📦 **存储桶操作**  | 列出、创建、删除存储桶      |
| 📁 **对象操作**   | 上传、下载、删除、复制对象    |
| 🔄 **数据迁移**   | 跨存储提供商数据迁移/同步    |
| 📝 **元数据迁移**  | 元数据完整迁移与校验       |
| 🔐 **ACL 管理** | ACL 查看、设置、复制     |
| ⚡ **增量同步**    | 支持增量同步与断点续传      |
| ✅ **数据校验**    | 内容/元数据/ACL 完整性校验 |

***

## 📦 安装指南

### 🔌 方式一：pip 安装

```bash
pip install skycli
```

### 💻 方式二：源码安装

```bash
git clone https://gitee.com/skybiubiu/skycli-object-migration.git
cd skycli-object-migration
pip install -e .
```

### 📋 依赖环境

| 依赖              | 版本要求      | 说明         |
| --------------- | --------- | ---------- |
| Python          | >= 3.8    | 运行环境       |
| boto3           | >= 1.26.0 | AWS S3 SDK |
| PyYAML          | >= 6.0    | 配置文件解析     |
| python-dateutil | >= 2.8.0  | 日期处理       |
| watchdog        | >= 3.0.0  | 文件监控       |

***

## 🚀 快速开始

### 1️⃣ 添加存储配置

```bash
# AWS S3
skycli config add --name aws-prod \
  --endpoint https://s3.amazonaws.com \
  --access-key AKIAXXX \
  --secret-key xxxxx \
  --region us-east-1

# MinIO
skycli config add --name minio-dev \
  --endpoint http://192.168.1.100:9000 \
  --access-key minioadmin \
  --secret-key minioadmin \
  --use-path-style

# 阿里云 OSS
skycli config add --name ali-oss \
  --endpoint https://oss-cn-hangzhou.aliyuncs.com \
  --access-key LTAIXXX \
  --secret-key xxxxx \
  --region cn-hangzhou
```

### 2️⃣ 测试连接

```bash
skycli config test --name aws-prod
```

### 3️⃣ 列出存储桶

```bash
skycli bucket list --source aws-prod
```

### 4️⃣ 列出对象

```bash
skycli object list --source aws-prod --bucket my-bucket
skycli object list --source aws-prod --bucket my-bucket --prefix logs/2024/
```

***

## 📚 命令参考

### ⚙️ 配置管理 (config)

| 命令                   | 说明     |
| -------------------- | ------ |
| `skycli config add`  | 添加配置   |
| `skycli config list` | 列出所有配置 |
| `skycli config test` | 测试连接   |
| `skycli config rm`   | 删除配置   |

<details>
<summary><b>📋 config add 完整参数</b></summary>

| 参数                 | 必填 | 说明                |
| ------------------ | -- | ----------------- |
| `--name`           | 是  | 配置名称              |
| `--endpoint`       | 是  | S3 endpoint 地址    |
| `--access-key`     | 是  | Access Key ID     |
| `--secret-key`     | 是  | Secret Access Key |
| `--region`         | 否  | 区域，默认 us-east-1   |
| `--use-path-style` | 否  | 使用 path-style 寻址  |
| `--no-verify-ssl`  | 否  | 禁用 SSL 验证         |
| `--profile`        | 否  | 配置文件名             |

</details>

<details>
<summary><b>📋 config list 完整参数</b></summary>

| 参数           | 说明       |
| ------------ | -------- |
| `--test-all` | 测试所有连接状态 |
| `--profile`  | 指定配置文件名  |

</details>

```bash
# 快速列出配置（不测试连接）
skycli config list

# 列出配置并测试连接状态
skycli config list --test-all
```

***

## 📦 存储桶操作 (bucket)

| 命令                     | 说明      |
| ---------------------- | ------- |
| `skycli bucket list`   | 列出存储桶   |
| `skycli bucket info`   | 查看存储桶信息 |
| `skycli bucket create` | 创建存储桶   |
| `skycli bucket rm`     | 删除存储桶   |

### 示例

```bash
# 列出存储桶
skycli bucket list --source aws-prod

# 查看存储桶详情
skycli bucket info --source aws-prod --bucket my-bucket

# 创建存储桶
skycli bucket create --source aws-prod --bucket new-bucket --region us-west-2

# 删除存储桶
skycli bucket rm --source aws-prod --bucket old-bucket --force
```

***

## 📁 对象操作 (object)

| 命令                   | 说明     |
| -------------------- | ------ |
| `skycli object list` | 列出对象   |
| `skycli object put`  | 上传对象   |
| `skycli object get`  | 下载对象   |
| `skycli object rm`   | 删除对象   |
| `skycli object info` | 查看对象信息 |
| `skycli object cp`   | 复制对象   |

### 示例

```bash
# 上传文件
skycli object put --source aws-prod --bucket my-bucket \
  --key backups/database.sql \
  --file /data/backup.sql \
  --metadata "project=database,env=prod" \
  --content-type application/sql \
  --storage-class STANDARD_IA

# 下载文件
skycli object get --source aws-prod --bucket my-bucket \
  --key backups/database.sql \
  --file /data/restore.sql

# 查看对象详情
skycli object info --source aws-prod --bucket my-bucket \
  --key logs/app.log \
  --include-metadata \
  --include-acl

# 复制对象 (保留元数据和ACL)
skycli object cp \
  --source aws-prod --source-bucket bucket1 --source-key logs/app.log \
  --target minio-dev --target-bucket bucket2 --target-key backup/app.log \
  --preserve-metadata \
  --preserve-acl
```

<details>
<summary><b>📋 object list 完整参数</b></summary>

| 参数            | 说明                |
| ------------- | ----------------- |
| `--source`    | 配置名称              |
| `--bucket`    | 存储桶名称             |
| `--prefix`    | 前缀过滤              |
| `--delimiter` | 分隔符               |
| `--max-keys`  | 最大返回数量            |
| `--output`    | 输出格式 (json/table) |

</details>

***

## 📝 元数据管理 (metadata)

| 命令                    | 说明    |
| --------------------- | ----- |
| `skycli metadata get` | 查看元数据 |
| `skycli metadata set` | 设置元数据 |

### 示例

```bash
# 查看对象元数据
skycli metadata get --source aws-prod --bucket my-bucket --key logs/app.log

# 设置元数据 (替换模式)
skycli metadata set --source aws-prod --bucket my-bucket \
  --key logs/app.log \
  --metadata "env=prod,version=2.0" \
  --operation REPLACE

# 设置元数据 (合并模式)
skycli metadata set --source aws-prod --bucket my-bucket \
  --key logs/app.log \
  --metadata "release-date=2024-01-15" \
  --operation COPY
```

***

## 🔐 ACL 管理 (acl)

| 命令               | 说明     |
| ---------------- | ------ |
| `skycli acl get` | 查看 ACL |
| `skycli acl set` | 设置 ACL |
| `skycli acl cp`  | 复制 ACL |

### 示例

```bash
# 查看对象 ACL
skycli acl get --source aws-prod --bucket my-bucket --key document.pdf

# 设置 ACL
skycli acl set --source aws-prod --bucket my-bucket \
  --key document.pdf \
  --acl public-read

# 复制 ACL
skycli acl cp \
  --source aws-prod --source-bucket bucket1 --source-key original.txt \
  --target minio-dev --target-bucket bucket2 --target-key copy.txt
```

***

## 🔄 数据同步 (sync)

> `sync` 命令统一了数据迁移和增量同步功能。通过 `--since`、`--since-last-sync` 或 `--delete` 参数可启用增量同步模式。

### sync run - 执行同步/迁移

```bash
# 完整迁移（无增量参数）
skycli sync run \
  --source aws-prod --source-bucket src-bucket \
  --target minio-dev --target-bucket dst-bucket

# 增量同步（自指定时间以来修改的对象）
skycli sync run \
  --source aws-prod --source-bucket data \
  --target minio-dev --target-bucket backup \
  --since 2024-01-01T00:00:00Z

# 增量同步（自上次同步以来修改的对象）
skycli sync run \
  --source aws-prod --source-bucket data \
  --target minio-dev --target-bucket backup \
  --since-last-sync

# 同步+删除（目标中有但源中已删除的对象）
skycli sync run \
  --source aws-prod --source-bucket data \
  --target minio-dev --target-bucket backup \
  --since-last-sync \
  --delete
```

<details>
<summary><b>📋 sync run 完整参数</b></summary>

| 参数                    | 必填 | 说明                    |
| --------------------- | -- | --------------------- |
| `--source`            | 是  | 源配置名称                 |
| `--source-bucket`     | 是  | 源存储桶                  |
| `--source-prefix`     | 否  | 源前缀                   |
| `--target`            | 是  | 目标配置名称                |
| `--target-bucket`     | 是  | 目标存储桶                 |
| `--target-prefix`     | 否  | 目标前缀                  |
| `--since`             | 否  | 同步指定时间之后修改的对象 (ISO格式) |
| `--since-last-sync`   | 否  | 同步上次同步之后修改的对象         |
| `--delete`            | 否  | 删除目标中存在但源中已不存在的对象     |
| `--threads`           | 否  | 并发线程数，默认 10           |
| `--part-size`         | 否  | 分块大小(MB)，默认 8         |
| `--storage-class`     | 否  | 目标存储类别                |
| `--preserve-metadata` | 否  | 保留原始元数据               |
| `--preserve-acl`      | 否  | 保留原始 ACL              |
| `--exclude`           | 否  | 排除匹配模式（支持通配符）         |
| `--include`           | 否  | 仅包含匹配模式（支持通配符）        |
| `--dry-run`           | 否  | 预览模式，不执行实际迁移          |
| `--resume`            | 否  | 从断点继续                 |
| `--profile`           | 否  | 配置文件名                 |
| `--output`            | 否  | 输出格式 (json/table)     |
| `--quiet`             | 否  | 静默模式                  |

</details>

| 命令                   | 说明      |
| -------------------- | ------- |
| `skycli sync run`    | 执行同步/迁移 |
| `skycli sync list`   | 查看同步历史  |
| `skycli sync status` | 查看同步状态  |

### 示例

```bash
# 预览同步（dry-run，不实际执行）
skycli sync run \
  --source aws-prod --source-bucket src-bucket \
  --target minio-dev --target-bucket dst-bucket \
  --dry-run

# 查看同步历史
skycli sync list --limit 10

# 查看同步状态
skycli sync status --migration-id sync-20240115-xxx

# 复杂迁移示例：指定存储类、保留元数据ACL、排除临时文件
skycli sync run \
  --source aws-prod --source-bucket src-bucket \
  --target minio-dev --target-bucket dst-bucket \
  --source-prefix data/ \
  --target-prefix archive/data/ \
  --storage-class GLACIER \
  --preserve-metadata \
  --preserve-acl \
  --exclude "*.tmp" \
  --exclude "temp/*" \
  --exclude ".git/*" \
  --threads 20 \
  --part-size 16
```

<details>
<summary><b>📋 同步模式说明</b></summary>

| 模式   | 参数组合                            | 说明                 |
| ---- | ------------------------------- | ------------------ |
| 迁移模式 | 无 `--since`、`--since-last-sync` | 一次性完整迁移所有对象        |
| 增量同步 | `--since` 或 `--since-last-sync` | 只同步指定时间/上次同步后变化的对象 |
| 镜像模式 | `--since-last-sync --delete`    | 增量同步并删除目标中多余的对象    |

</details>

***

## ✅ 数据校验 (validate)

| 命令                       | 说明     |
| ------------------------ | ------ |
| `skycli validate run`    | 执行校验   |
| `skycli validate report` | 查看报告   |
| `skycli validate list`   | 列出历史校验 |

### 示例

```bash
# 完整校验 (内容+元数据+ACL)
skycli validate run \
  --source aws-prod --source-bucket bucket1 \
  --target minio-dev --target-bucket bucket2

# 仅校验内容
skycli validate run \
  --source aws-prod --source-bucket bucket1 \
  --target minio-dev --target-bucket bucket2 \
  --check content

# 仅校验元数据
skycli validate run \
  --source aws-prod --source-bucket bucket1 \
  --target minio-dev --target-bucket bucket2 \
  --check metadata

# 仅校验 ACL
skycli validate run \
  --source aws-prod --source-bucket bucket1 \
  --target minio-dev --target-bucket bucket2 \
  --check acl

# 指定元数据字段
skycli validate run \
  --source aws-prod --source-bucket bucket1 \
  --target minio-dev --target-bucket bucket2 \
  --check metadata \
  --fields ContentType,CacheControl,Metadata

# 查看校验报告
skycli validate report --validation-id val-20240115-001
```

<details>
<summary><b>📋 validate run 完整参数</b></summary>

| 参数          | 说明                             |
| ----------- | ------------------------------ |
| `--check`   | 校验类型: content/metadata/acl/all |
| `--fields`  | 指定元数据字段 (逗号分隔)                 |
| `--prefix`  | 对象前缀过滤                         |
| `--threads` | 并发线程数                          |

</details>

***

## ⚙️ 全局参数与输出格式

### 📤 输出格式

所有命令支持 `--output` 参数指定输出格式：

| 格式      | 说明        |
| ------- | --------- |
| `table` | 表格格式 (默认) |
| `json`  | JSON 格式   |

### 🔧 全局参数

| 参数          | 说明       |
| ----------- | -------- |
| `--profile` | 使用指定配置文件 |
| `--quiet`   | 静默模式     |
| `--debug`   | 调试模式     |

***

## 📋 配置说明

### 📁 配置文件位置

配置文件位于 `~/.skycli/config.yaml`

### 📝 配置示例

```yaml
default: aws-prod

profiles:
  aws-prod:
    endpoint: https://s3.amazonaws.com
    access_key: AKIAXXX
    secret_key: xxxxx
    region: us-east-1
    use_path_style: false
    verify_ssl: true

  minio-dev:
    endpoint: http://192.168.1.100:9000
    access_key: minioadmin
    secret_key: minioadmin
    use_path_style: true
    verify_ssl: false
```

***

## 📂 状态文件

同步和校验的状态信息保存在:

| 目录                              | 说明    |
| ------------------------------- | ----- |
| `~/.skycli/checkpoints/`        | 检查点文件 |
| `~/.skycli/sync-state/`         | 同步状态  |
| `~/.skycli/validation-reports/` | 校验报告  |

***

## 📦 存储类别

| 存储类别                  | 说明           |
| --------------------- | ------------ |
| `STANDARD`            | 标准存储         |
| `STANDARD_IA`         | 低频访问存储       |
| `GLACIER`             | Glacier 归档存储 |
| `DEEP_ARCHIVE`        | 深度归档         |
| `INTELLIGENT_TIERING` | 智能分层         |

***

## 🔐 权限说明

### Canned ACL

| ACL                  | 说明    |
| -------------------- | ----- |
| `private`            | 私有    |
| `public-read`        | 公有读   |
| `public-read-write`  | 公有读写  |
| `authenticated-read` | 认证用户读 |
| `log-delivery-write` | 日志写入  |

### 权限级别

| 权限             | 说明     |
| -------------- | ------ |
| `READ`         | 读取     |
| `WRITE`        | 写入     |
| `READ_ACP`     | 读取 ACL |
| `WRITE_ACP`    | 写入 ACL |
| `FULL_CONTROL` | 完全控制   |

***

## ❓ 常见问题

<details>
<summary><b>Q: 连接失败怎么办？</b></summary>

1. 检查 endpoint 是否正确
2. 确认 access-key 和 secret-key 有效
3. 使用 `--no-verify-ssl` 测试是否 SSL 问题
4. 使用 `skycli config test --name xxx` 测试连接

</details>

<details>
<summary><b>Q: 迁移中断如何续传？</b></summary>

```bash
skycli sync run \
  --source aws-prod --source-bucket src \
  --target minio-dev --target-bucket dst \
  --resume
```

</details>

<details>
<summary><b>Q: 如何只迁移特定类型的文件？</b></summary>

```bash
skycli sync run \
  --source aws-prod --source-bucket src \
  --target minio-dev --target-bucket dst \
  --include "*.jpg" \
  --include "*.png" \
  --include "*.pdf"
```

</details>

<details>
<summary><b>Q: 如何排除不需要迁移的文件？</b></summary>

```bash
skycli sync run \
  --source aws-prod --source-bucket src \
  --target minio-dev --target-bucket dst \
  --exclude "temp/*" \
  --exclude "*.tmp" \
  --exclude ".git/*"
```

</details>

***

## 📜 更新日志 (Changelog)

### 🆕 v0.4.1 (2026-04-12)

**测试基础设施**

- 引入 `moto[s3]` 5.x 进行 S3 功能测试，无需真实 AWS 环境
- 实现双模式测试架构：支持 Moto Mock 和真实 S3 两种测试模式
- 新增 `tests/test_skyclient_moto.py` 包含 12 个完整的 Moto 测试用例
- 更新 `tests/conftest.py` 添加 `moto_mock` fixture 和环境变量控制
- 创建 `pytest.ini` 配置文件，支持测试标记和过滤
- 所有 123 个测试通过，保持 100% 测试覆盖率

**功能改进**

- 修复 `SkyClient.create_bucket()` 方法自动使用实例 region 参数
- 解决 Moto 5 与 boto3 在 `us-east-1` region 的兼容性问题
- 优化测试配置管理，支持通过 `.env` 文件切换测试模式

**依赖更新**

- 新增 `moto[s3]>=5.0.0` 和 `responses>=0.23.0` 作为测试依赖
- 更新 `pyproject.toml` 和 `requirements.txt`

### 🆕 v0.4.0 (2026-04-12)

**国际化 (i18n) 支持**

- 新增 `i18n.py` 模块，使用标准库 `gettext` 实现国际化
- 新增 `locale/` 目录，包含中文 (`zh_CN`) 和英文 (`en`) 翻译文件
- 重构 `skycli.py` 所有用户可见字符串使用 `_()` 翻译函数
- 支持通过配置文件切换语言（默认中文）
- 修复进度提示等所有 CLI 输出的国际化问题

**测试改进**

- 更新测试用例支持多语言输出断言
- 添加 `i18n` fixture 确保测试环境语言一致性
- 完整单元测试套件：111 个测试通过，1 个跳过

**版本管理优化**

- 遵循 PEP 440 版本规范
- 优化 `_version.py` 添加类型提示和完整文档
- 提供版本一致性检查脚本 `check_version.py`
- 提供版本更新脚本 `update_version.py`

**代码质量**

- 符合 Python 最佳实践规范（综合评分 90/100）
- 完整的类型注解覆盖
- 改进的错误处理和日志记录

### 🆕 v0.3.6 (2026-04-12)

**代码质量改进**

- 新增 `constants.py`，将硬编码状态消息提取为常量
- `skycli.py` 中的状态消息改用常量引用
- 为 `skyclient.py` 的 `_create_client()` / `_create_resource()` 添加 docstrings
- 为 `skyconfig.py` 的配置管理方法添加 docstrings

### 🆕 v0.3.5 (2026-04-12)

**新增测试**

- 新增 `tests/test_skyreport.py`，包含 33 个测试用例
- 覆盖 `ReportGenerator` 所有方法：格式化、报告生成、预览功能
- 达到 `skyreport.py` 100% 代码覆盖率

**测试改进**

- 完整单元测试套件：111 个测试通过，1 个跳过

### 🆕 v0.3.4 (2026-04-12)

**Bug 修复**

- 修复 `SyncStatus` 枚举 JSON 序列化错误：`Object of type SyncStatus is not JSON serializable`
- 修复 `--delete` 模式删除统计未在报告中显示的问题

**代码改进**

- 同步模式使用 `generate_sync_report()` 生成报告，迁移模式使用 `generate_migration_report()`
- 新增 `_sync_delete()` 单元测试，验证删除孤儿对象和前缀处理

**新增测试**

- `test_sync_delete_removes_orphan_objects` - 验证删除孤儿对象
- `test_sync_delete_with_prefix` - 验证带前缀的删除
- `test_get_summary_returns_string_status` - 验证状态返回字符串

### 🆕 v0.3.3 (2026-04-12)

**Gitee 仓库链接修复**

- 修复源码安装命令中的 GitHub 链接为 Gitee 仓库地址
- 修复贡献指南中的克隆命令和目录名称
- 目录名称统一为 `skycli-object-migration`

### 🆕 v0.3.2 (2026-04-12)

**README 优化**

- 添加 PyPI、License、Python版本、Platform 徽章
- 添加完整导航目录，提升文档可读性
- 功能特性使用表格 + emoji 美化展示
- 命令参考模块化，添加视觉分隔线
- 参数表格使用折叠块 (`<details>`) 精简文档
- 常见问题使用折叠块美化展示
- 更新日志添加 emoji 标识版本类型
- 新增贡献指南章节
- 新增许可证章节和页脚

### 🆕 v0.3.1 (2026-04-12)

**版本管理优化**

- 符合 PEP 621 标准的 `pyproject.toml` 配置
- 统一版本管理：单一事实源设计
- `pyproject.toml` 使用动态版本声明，从 `_version.py` 读取
- `setup.py` 通过 `get_version()` 从 `_version.py` 读取
- 新增 `update_version.py` 自动化版本更新脚本
- 新增 `check_version.py` 版本一致性验证工具
- 支持 `--fix` 参数自动修复版本不一致

### 🆕 v0.3.0 (2026-04-12)

**代码质量优化**

- 使用 `dataclass` 重构 `SyncTask` 类，代码更简洁清晰
- 新增 `SyncStatus` 枚举类型，替代字符串状态
- 新增 `SyncResult` 和 `SyncProgress` 数据类，统一返回值格式
- 常量添加详细注释说明用途和单位

**常量定义**

- `LARGE_FILE_THRESHOLD = 100 MiB` - 触发分段上传的文件大小阈值
- `CHECKPOINT_BATCH_SIZE = 100` - 每 N 个对象批量保存一次 checkpoint

**类型安全增强**

- 所有方法返回值使用明确的数据类而非 Dict
- 状态管理使用 Enum 而非字符串，避免拼写错误
- 改进类型注解，提升 IDE 支持

### 🐛 v0.2.3 (2026-04-12)

**大文件处理优化**

- 大文件（>100MB）采用 `upload_file` 分段上传，避免内存溢出
- 临时文件下载到本地后上传，上传完成后自动清理
- 新增 `_migrate_large_object` 和 `_migrate_small_object` 方法分离处理逻辑

**Checkpoint 性能优化**

- 批量 checkpoint 保存（每 100 个对象保存一次），减少磁盘 I/O
- 新增 `_checkpoint_cache` 和 `_checkpoint_dirty` 状态追踪
- 支持强制保存 `force=True` 参数

**小文件处理优化**

- 新增 `_prefetch_metadata` 方法预取大文件元数据，减少串行请求
- 元数据缓存避免重复 HEAD 请求

**MinIO 兼容性优化**

- ACL 复制失败时捕获 `NotImplemented` 和 `MinIO` 相关异常
- 避免因 ACL 不支持导致整个同步失败

**日志和调试**

- 添加 `logging` 模块支持，便于调试和问题排查
- 优化 `run()` 方法中的日志输出

### 🐛 v0.2.2 (2026-04-12)

**版本管理优化**

- 新增 `_version.py` 统一版本管理模块
- 所有版本信息集中维护，避免多文件版本不一致
- CLI 支持 `--version` 参数查看版本号

**Bug 修复**

- 修复 ACL 处理相关问题
- 改进元数据复制逻辑
- 优化并发同步性能

### ✨ v0.2.0 (2026-04-11)

**重大更新：合并 sync 和 migrate 命令**

- 统一 `sync` 命令，整合原 `migrate` 和 `sync` 的所有功能
- 删除独立的 `migrate` 命令，现通过 `sync` 命令统一提供
- 新增 `--since` 参数支持指定时间以来的增量同步
- 新增 `--since-last-sync` 参数支持自上次同步以来的增量同步
- 新增 `--delete` 参数支持目标端删除操作（镜像模式）
- 增强断点续传功能，支持 checkpoint 机制
- 优化并发处理，使用 ThreadPoolExecutor 提升性能

**功能增强**

- 实现 `--dry-run` 参数，对比源和目标显示同步差异但不执行
- 删除 `preview` 子命令，统一由 `--dry-run` 提供预览功能
- 合并 `migrate list` 到 `sync list`
- 合并 `migrate status` 到 `sync status`
- 统一 `get_sync_history()` 函数替代原 `get_migration_history()`
- 统一 `get_sync()` 函数替代原 `get_migration()`

### ✨ v0.1.0 (2026-04-10)

**初始版本**

- 配置管理（添加、列出、测试、删除）
- 存储桶操作（列出、创建、删除、信息）
- 对象操作（列出、上传、下载、删除、复制）
- 元数据管理（查看、设置）
- ACL管理（查看、设置、复制）
- 数据迁移（`migrate` 命令）
- 增量同步（`sync` 命令）
- 数据校验（内容、元数据、ACL）

***

## 🤝 贡献指南

欢迎提交 Pull Request 或 Issue！

### 开发环境搭建

```bash
# 克隆仓库
git clone https://gitee.com/skybiubiu/skycli-object-migration.git
cd skycli-object-migration

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/
```

### 代码规范

- 遵循 PEP 8 代码规范
- 使用 type hints 标注类型
- 提交前运行 `check_version.py` 确保版本一致性

***

## 📄 许可证

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

MIT License - 详见 [LICENSE](LICENSE) 文件

***

<p align="center">
  <sub>Made with ❤️ by SkyCLI Team</sub>
</p>
