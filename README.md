# SkyCLI - S3 兼容对象存储管理/迁移工具

基于 AWS S3 SDK (boto3) 开发的命令行工具，支持管理和迁移 S3 协议兼容的对象存储服务，包括 AWS S3、MinIO、Ceph、阿里云 OSS、腾讯云 COS 等。

## 功能特性

- 多存储源配置管理
- 存储桶和对象操作
- 跨存储提供商数据迁移
- 元数据与 ACL 完整迁移与校验
- 增量同步与断点续传
- 数据完整性校验 (内容/元数据/ACL)

## 安装

### 方式一：pip 安装

```bash
pip install skycli
```

### 方式二：源码安装

```bash
cd sky_object_migration
pip install -e .
```

### 依赖

- Python >= 3.8
- boto3 >= 1.26.0
- PyYAML >= 6.0
- python-dateutil >= 2.8.0

## 快速开始

### 1. 添加存储配置

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

### 2. 测试连接

```bash
skycli config test --name aws-prod
```

### 3. 列出存储桶

```bash
skycli bucket list --source aws-prod
```

### 4. 列出对象

```bash
skycli object list --source aws-prod --bucket my-bucket
skycli object list --source aws-prod --bucket my-bucket --prefix logs/2024/
```

## 配置管理命令 (config)

| 命令                   | 说明     |
| -------------------- | ------ |
| `skycli config add`  | 添加配置   |
| `skycli config list` | 列出所有配置 |
| `skycli config test` | 测试连接   |
| `skycli config rm`   | 删除配置   |

### config add 参数

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

## 存储桶命令 (bucket)

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

## 对象命令 (object)

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

### object list 参数

| 参数            | 说明                |
| ------------- | ----------------- |
| `--source`    | 配置名称              |
| `--bucket`    | 存储桶名称             |
| `--prefix`    | 前缀过滤              |
| `--delimiter` | 分隔符               |
| `--max-keys`  | 最大返回数量            |
| `--output`    | 输出格式 (json/table) |

## 元数据命令 (metadata)

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

## ACL 命令 (acl)

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

## 迁移命令 (migrate)

### migrate run - 执行迁移

```bash
skycli migrate run \
  --source aws-prod --source-bucket src-bucket \
  --target minio-dev --target-bucket dst-bucket \
  [--source-prefix path/] \
  [--target-prefix archive/path/] \
  [--threads 10] \
  [--storage-class GLACIER] \
  [--preserve-metadata] \
  [--preserve-acl] \
  [--exclude "*.tmp"] \
  [--include "*.jpg"] \
  [--resume]
```

### migrate preview - 预览迁移

```bash
skycli migrate preview \
  --source aws-prod --source-bucket src-bucket \
  --target minio-dev --target-bucket dst-bucket
```

### migrate list - 查看迁移历史

```bash
skycli migrate list --limit 10
```

### migrate status - 查看迁移状态

```bash
skycli migrate status --migration-id mig-20240115-xxx
```

### 参数说明

| 参数                    | 说明            |
| --------------------- | ------------- |
| `--source`            | 源配置名称         |
| `--source-bucket`     | 源存储桶          |
| `--source-prefix`     | 源前缀           |
| `--target`            | 目标配置名称        |
| `--target-bucket`     | 目标存储桶         |
| `--target-prefix`     | 目标前缀          |
| `--threads`           | 并发线程数，默认 10   |
| `--part-size`         | 分块大小(MB)，默认 8 |
| `--storage-class`     | 目标存储类别        |
| `--preserve-metadata` | 保留原始元数据       |
| `--preserve-acl`      | 保留原始 ACL      |
| `--exclude`           | 排除匹配模式        |
| `--include`           | 仅包含匹配模式       |
| `--dry-run`           | 预览模式，不执行      |
| `--resume`            | 从断点继续         |
| `--profile`           | 配置文件名         |
| `--output`            | 输出格式          |

## 同步命令 (sync)

### sync run - 执行同步

```bash
skycli sync run \
  --source aws-prod --source-bucket data \
  --target minio-dev --target-bucket backup \
  [--source-prefix logs/] \
  [--target-prefix archive/logs/] \
  [--since 2024-01-01] \
  [--since-last-sync] \
  [--delete] \
  [--threads 10]
```

### 参数说明

| 参数                  | 说明                |
| ------------------- | ----------------- |
| `--since`           | 同步指定时间之后修改的对象     |
| `--since-last-sync` | 同步上次同步之后修改的对象     |
| `--delete`          | 删除目标中存在但源中已不存在的对象 |

## 校验命令 (validate)

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

### validate run 参数

| 参数          | 说明                             |
| ----------- | ------------------------------ |
| `--check`   | 校验类型: content/metadata/acl/all |
| `--fields`  | 指定元数据字段 (逗号分隔)                 |
| `--prefix`  | 对象前缀过滤                         |
| `--threads` | 并发线程数                          |

## 输出格式

所有命令支持 `--output` 参数指定输出格式：

```bash
--output json   # JSON 格式
--output table   # 表格格式 (默认)
```

## 全局参数

| 参数          | 说明       |
| ----------- | -------- |
| `--profile` | 使用指定配置文件 |
| `--quiet`   | 静默模式     |
| `--debug`   | 调试模式     |

## 配置文件

配置文件位于 `~/.skycli/config.yaml`

### 示例配置

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

## 迁移状态文件

迁移和同步的状态信息保存在:

- 迁移检查点: `~/.skycli/checkpoints/`
- 同步状态: `~/.skycli/sync-state/`
- 校验报告: `~/.skycli/validation-reports/`

## 存储类别

支持以下存储类别:

- `STANDARD` - 标准存储
- `STANDARD_IA` - 低频访问存储
- `GLACIER` - Glacier 归档存储
- `DEEP_ARCHIVE` - 深度归档
- `INTELLIGENT_TIERING` - 智能分层

## 权限说明

### Canned ACL

- `private` - 私有
- `public-read` - 公有读
- `public-read-write` - 公有读写
- `authenticated-read` - 认证用户读
- `log-delivery-write` - 日志写入

### 权限级别

- `READ` - 读取
- `WRITE` - 写入
- `READ_ACP` - 读取 ACL
- `WRITE_ACP` - 写入 ACL
- `FULL_CONTROL` - 完全控制

## 常见问题

### Q: 连接失败怎么办？

1. 检查 endpoint 是否正确
2. 确认 access-key 和 secret-key 有效
3. 使用 `--no-verify-ssl` 测试是否 SSL 问题
4. 使用 `skycli config test --name xxx` 测试连接

### Q: 迁移中断如何续传？

```bash
skycli migrate run \
  --source aws-prod --source-bucket src \
  --target minio-dev --target-bucket dst \
  --resume
```

### Q: 如何只迁移特定类型的文件？

```bash
skycli migrate run \
  --source aws-prod --source-bucket src \
  --target minio-dev --target-bucket dst \
  --include "*.jpg" \
  --include "*.png" \
  --include "*.pdf"
```

### Q: 如何排除不需要迁移的文件？

```bash
skycli migrate run \
  --source aws-prod --source-bucket src \
  --target minio-dev --target-bucket dst \
  --exclude "temp/*" \
  --exclude "*.tmp" \
  --exclude ".git/*"
```

## 许可证

MIT License
