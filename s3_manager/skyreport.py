import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class ReportGenerator:
    @staticmethod
    def format_size(size_bytes: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"

    @staticmethod
    def format_duration(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"

    @staticmethod
    def generate_migration_report(summary: Dict, output_format: str = "table") -> str:
        if output_format == "json":
            return json.dumps(summary, indent=2)

        def fmt(label, value):
            return f"  {label:<8} {value}"

        lines = []
        lines.append("=" * 60)
        lines.append("          迁 移 报 告")
        lines.append("=" * 60)
        lines.append("")
        lines.append(fmt("迁移ID:", summary.get('migration_id', 'N/A')))
        lines.append(fmt("状态:", summary.get('status', 'N/A').upper()))
        lines.append(fmt("开始时间:", summary.get('start_time', 'N/A')))
        lines.append(fmt("结束时间:", summary.get('end_time', 'N/A')))
        lines.append(fmt("持续时间:", ReportGenerator.format_duration(summary.get('duration_seconds', 0) or 0)))
        lines.append("")
        lines.append("  源:")
        lines.append(fmt("  存储桶:", summary.get('source_bucket', 'N/A')))
        lines.append(fmt("  前缀:", summary.get('source_prefix', '')))
        lines.append("")
        lines.append("  目标:")
        lines.append(fmt("  存储桶:", summary.get('target_bucket', 'N/A')))
        lines.append(fmt("  前缀:", summary.get('target_prefix', '')))
        lines.append("")
        lines.append("  选项:")
        lines.append(fmt("  保留元数据:", '是' if summary.get('preserve_metadata', False) else '否'))
        lines.append(fmt("  保留ACL:", '是' if summary.get('preserve_acl', False) else '否'))
        lines.append("")
        lines.append("  统计:")
        lines.append(fmt("  对象总数:", f"{summary.get('total_objects', 0):,}"))
        lines.append(fmt("  已处理:", f"{summary.get('processed_objects', 0):,}"))
        lines.append(fmt("  失败:", f"{summary.get('failed_objects', 0):,}"))
        lines.append(fmt("  总大小:", ReportGenerator.format_size(summary.get('total_bytes', 0))))
        lines.append(fmt("  已传输:", ReportGenerator.format_size(summary.get('transferred_bytes', 0))))

        if summary.get('failed_list'):
            lines.append("")
            lines.append("  失败对象 (前10个):")
            for item in summary['failed_list'][:10]:
                lines.append(f"    - {item.get('key', 'N/A')}: {item.get('error', '未知错误')}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    @staticmethod
    def generate_sync_report(summary: Dict, output_format: str = "table") -> str:
        if output_format == "json":
            return json.dumps(summary, indent=2)

        def fmt(label, value):
            return f"  {label:<8} {value}"

        lines = []
        lines.append("=" * 60)
        lines.append("          同 步 报 告")
        lines.append("=" * 60)
        lines.append("")
        lines.append(fmt("同步ID:", summary.get('sync_id', 'N/A')))
        lines.append(fmt("状态:", summary.get('status', 'N/A').upper()))
        lines.append(fmt("开始时间:", summary.get('start_time', 'N/A')))
        lines.append(fmt("结束时间:", summary.get('end_time', 'N/A')))
        lines.append(fmt("持续时间:", ReportGenerator.format_duration(summary.get('duration_seconds', 0) or 0)))
        lines.append("")
        lines.append("  源:")
        lines.append(fmt("  存储桶:", summary.get('source_bucket', 'N/A')))
        lines.append(fmt("  前缀:", summary.get('source_prefix', '')))
        lines.append("")
        lines.append("  目标:")
        lines.append(fmt("  存储桶:", summary.get('target_bucket', 'N/A')))
        lines.append(fmt("  前缀:", summary.get('target_prefix', '')))
        lines.append("")
        lines.append("  选项:")
        lines.append(fmt("  保留元数据:", '是' if summary.get('preserve_metadata', False) else '否'))
        lines.append(fmt("  保留ACL:", '是' if summary.get('preserve_acl', False) else '否'))
        if summary.get("dry_run", False):
            lines.append(fmt("  模式:", '预览模式 (dry-run)'))
        lines.append("")
        lines.append("  统计:")
        lines.append(fmt("  同步对象数:", f"{summary.get('total_objects', 0):,}"))
        lines.append(fmt("  已上传:", f"{summary.get('uploaded', 0):,}"))
        lines.append(fmt("  已删除:", f"{summary.get('deleted', 0):,}"))
        lines.append(fmt("  已跳过:", f"{summary.get('skipped', 0):,}"))
        lines.append(fmt("  失败:", f"{summary.get('failed', 0):,}"))
        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    @staticmethod
    def generate_validation_report(report: Dict, output_format: str = "table") -> str:
        if output_format == "json":
            return json.dumps(report, indent=2)

        def fmt(label, value):
            return f"  {label:<10} {value}"

        summary = report.get("summary", {})

        lines = []
        lines.append("=" * 60)
        lines.append("         验 证 报 告")
        lines.append("=" * 60)
        lines.append("")
        lines.append(fmt("验证ID:", report.get('validation_id', 'N/A')))
        lines.append(fmt("时间戳:", report.get('timestamp', 'N/A')))
        lines.append(fmt("状态:", report.get('status', 'N/A').upper()))
        lines.append(fmt("持续时间:", ReportGenerator.format_duration(report.get('duration_seconds', 0) or 0)))
        lines.append("")
        lines.append("  源:")
        lines.append(fmt("  存储桶:", report.get('source_bucket', 'N/A')))
        lines.append(fmt("  前缀:", report.get('prefix', '')))
        lines.append("")
        lines.append("  目标:")
        lines.append(fmt("  存储桶:", report.get('target_bucket', 'N/A')))
        lines.append("")
        lines.append("  概要:")
        lines.append(fmt("  对象总数:", f"{summary.get('total_objects', 0):,}"))
        lines.append("")
        lines.append(fmt("  内容检查:", ""))
        lines.append(fmt("  通过:", f"{summary.get('content_passed', 0):,}"))
        lines.append(fmt("  失败:", f"{summary.get('content_failed', 0):,}"))
        lines.append("")
        lines.append(fmt("  元数据检查:", ""))
        if report.get('check_metadata', True):
            lines.append(fmt("  通过:", f"{summary.get('metadata_passed', 0):,}"))
            lines.append(fmt("  失败:", f"{summary.get('metadata_failed', 0):,}"))
        else:
            lines.append(fmt("  跳过:", f"{summary.get('metadata_skipped', 0):,}"))
        lines.append("")
        lines.append(fmt("  ACL检查:", ""))
        if report.get('check_acl', True):
            lines.append(fmt("  通过:", f"{summary.get('acl_passed', 0):,}"))
            lines.append(fmt("  失败:", f"{summary.get('acl_failed', 0):,}"))
        else:
            lines.append(fmt("  跳过:", f"{summary.get('acl_skipped', 0):,}"))

        if report.get("failed_objects"):
            lines.append("")
            lines.append("  失败对象 (前10个):")
            for obj in report["failed_objects"][:10]:
                lines.append(f"    - {obj.get('key', 'N/A')}")
                for error in obj.get("errors", []):
                    lines.append(f"      {error}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    @staticmethod
    def generate_migration_preview(
        objects: List[Dict],
        source_bucket: str,
        target_bucket: str,
        source_prefix: str,
        output_format: str = "table"
    ) -> str:
        if output_format == "json":
            return json.dumps({
                "source_bucket": source_bucket,
                "target_bucket": target_bucket,
                "source_prefix": source_prefix,
                "objects": objects
            }, indent=2)

        def fmt(label, value):
            return f"  {label:<8} {value}"

        total_size = sum(obj.get("Size", 0) for obj in objects)

        lines = []
        lines.append("=" * 60)
        lines.append("         迁 移 预 览")
        lines.append("=" * 60)
        lines.append("")
        lines.append(fmt("源:", source_bucket))
        lines.append(fmt("前缀:", source_prefix or '/'))
        lines.append(fmt("目标:", target_bucket))
        lines.append("")
        lines.append("  统计:")
        lines.append(fmt("  对象总数:", f"{len(objects):,}"))
        lines.append(fmt("  总大小:", ReportGenerator.format_size(total_size)))
        lines.append("")
        lines.append("  待迁移对象:")
        header = f"  {'对象键:<38'} {'大小':>12} {'最后修改':<20}"
        lines.append(header)
        lines.append("  " + "-" * 56)

        for obj in objects[:50]:
            key = obj.get("Key", "")[:38] if len(obj.get("Key", "")) > 38 else obj.get("Key", "")
            size = ReportGenerator.format_size(obj.get("Size", 0))
            last_modified = obj.get("LastModified", "")[:19] if obj.get("LastModified") else ""
            lines.append(f"  {key:<38} {size:>12} {last_modified:<20}")

        if len(objects) > 50:
            lines.append(f"  ... 还有 {len(objects) - 50} 个对象")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    @staticmethod
    def generate_sync_preview(
        objects: List[Dict],
        source_bucket: str,
        target_bucket: str,
        since: Optional[str],
        output_format: str = "table"
    ) -> str:
        if output_format == "json":
            return json.dumps({
                "source_bucket": source_bucket,
                "target_bucket": target_bucket,
                "since": since,
                "objects": objects
            }, indent=2)

        def fmt(label, value):
            return f"  {label:<8} {value}"

        total_size = sum(obj.get("Size", 0) for obj in objects)

        lines = []
        lines.append("=" * 60)
        lines.append("          同 步 预 览")
        lines.append("=" * 60)
        lines.append("")
        lines.append(fmt("源:", source_bucket))
        lines.append(fmt("目标:", target_bucket))
        if since:
            lines.append(fmt("自:", since))
        lines.append("")
        lines.append("  统计:")
        lines.append(fmt("  同步对象数:", f"{len(objects):,}"))
        lines.append(fmt("  总大小:", ReportGenerator.format_size(total_size)))
        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)
