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

        lines = []
        lines.append("=" * 60)
        lines.append("           MIGRATION REPORT")
        lines.append("=" * 60)
        lines.append("")

        lines.append(f"Migration ID:    {summary.get('migration_id', 'N/A')}")
        lines.append(f"Status:          {summary.get('status', 'N/A').upper()}")
        lines.append(f"Start Time:      {summary.get('start_time', 'N/A')}")
        lines.append(f"End Time:       {summary.get('end_time', 'N/A')}")
        lines.append(f"Duration:        {ReportGenerator.format_duration(summary.get('duration_seconds', 0) or 0)}")
        lines.append("")

        lines.append("SOURCE:")
        lines.append(f"  Bucket:        {summary.get('source_bucket', 'N/A')}")
        lines.append(f"  Prefix:        {summary.get('source_prefix', '')}")
        lines.append("")

        lines.append("TARGET:")
        lines.append(f"  Bucket:        {summary.get('target_bucket', 'N/A')}")
        lines.append(f"  Prefix:        {summary.get('target_prefix', '')}")
        lines.append("")

        lines.append("STATISTICS:")
        lines.append(f"  Total Objects: {summary.get('total_objects', 0):,}")
        lines.append(f"  Processed:     {summary.get('processed_objects', 0):,}")
        lines.append(f"  Failed:        {summary.get('failed_objects', 0):,}")
        lines.append(f"  Total Size:    {ReportGenerator.format_size(summary.get('total_bytes', 0))}")
        lines.append(f"  Transferred:   {ReportGenerator.format_size(summary.get('transferred_bytes', 0))}")

        if summary.get('failed_list'):
            lines.append("")
            lines.append("FAILED OBJECTS (first 10):")
            for item in summary['failed_list'][:10]:
                lines.append(f"  - {item.get('key', 'N/A')}: {item.get('error', 'Unknown error')}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    @staticmethod
    def generate_sync_report(summary: Dict, output_format: str = "table") -> str:
        if output_format == "json":
            return json.dumps(summary, indent=2)

        lines = []
        lines.append("=" * 60)
        lines.append("           SYNC REPORT")
        lines.append("=" * 60)
        lines.append("")

        lines.append(f"Sync ID:         {summary.get('sync_id', 'N/A')}")
        lines.append(f"Status:          {summary.get('status', 'N/A').upper()}")
        lines.append(f"Start Time:      {summary.get('start_time', 'N/A')}")
        lines.append(f"End Time:       {summary.get('end_time', 'N/A')}")
        lines.append(f"Duration:        {ReportGenerator.format_duration(summary.get('duration_seconds', 0) or 0)}")
        lines.append("")

        lines.append("SOURCE:")
        lines.append(f"  Bucket:        {summary.get('source_bucket', 'N/A')}")
        lines.append(f"  Prefix:        {summary.get('source_prefix', '')}")
        lines.append("")

        lines.append("TARGET:")
        lines.append(f"  Bucket:        {summary.get('target_bucket', 'N/A')}")
        lines.append(f"  Prefix:        {summary.get('target_prefix', '')}")
        lines.append("")

        lines.append("STATISTICS:")
        lines.append(f"  Total to Sync: {summary.get('total_objects', 0):,}")
        lines.append(f"  Uploaded:      {summary.get('uploaded', 0):,}")
        lines.append(f"  Deleted:       {summary.get('deleted', 0):,}")
        lines.append(f"  Skipped:       {summary.get('skipped', 0):,}")
        lines.append(f"  Failed:        {summary.get('failed', 0):,}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    @staticmethod
    def generate_validation_report(report: Dict, output_format: str = "table") -> str:
        if output_format == "json":
            return json.dumps(report, indent=2)

        summary = report.get("summary", {})

        lines = []
        lines.append("=" * 60)
        lines.append("        VALIDATION REPORT")
        lines.append("=" * 60)
        lines.append("")

        lines.append(f"Validation ID:   {report.get('validation_id', 'N/A')}")
        lines.append(f"Timestamp:       {report.get('timestamp', 'N/A')}")
        lines.append(f"Status:          {report.get('status', 'N/A').upper()}")
        lines.append(f"Duration:        {ReportGenerator.format_duration(report.get('duration_seconds', 0) or 0)}")
        lines.append("")

        lines.append("SOURCE:")
        lines.append(f"  Bucket:        {report.get('source_bucket', 'N/A')}")
        lines.append(f"  Prefix:        {report.get('prefix', '')}")
        lines.append("")

        lines.append("TARGET:")
        lines.append(f"  Bucket:        {report.get('target_bucket', 'N/A')}")
        lines.append("")

        lines.append("SUMMARY:")
        lines.append(f"  Total Objects: {summary.get('total_objects', 0):,}")
        lines.append("")
        lines.append("  Content Check:")
        lines.append(f"    Passed:      {summary.get('content_passed', 0):,}")
        lines.append(f"    Failed:      {summary.get('content_failed', 0):,}")
        lines.append("")
        lines.append("  Metadata Check:")
        lines.append(f"    Passed:      {summary.get('metadata_passed', 0):,}")
        lines.append(f"    Failed:      {summary.get('metadata_failed', 0):,}")
        lines.append("")
        lines.append("  ACL Check:")
        lines.append(f"    Passed:      {summary.get('acl_passed', 0):,}")
        lines.append(f"    Failed:      {summary.get('acl_failed', 0):,}")

        if report.get("failed_objects"):
            lines.append("")
            lines.append("FAILED OBJECTS (first 10):")
            for obj in report["failed_objects"][:10]:
                lines.append(f"  - {obj.get('key', 'N/A')}")
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

        total_size = sum(obj.get("Size", 0) for obj in objects)

        lines = []
        lines.append("=" * 60)
        lines.append("        MIGRATION PREVIEW")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Source:      {source_bucket} (prefix: {source_prefix or '/'})")
        lines.append(f"Target:      {target_bucket}")
        lines.append("")
        lines.append("STATISTICS:")
        lines.append(f"  Total Objects: {len(objects):,}")
        lines.append(f"  Total Size:     {ReportGenerator.format_size(total_size)}")
        lines.append("")
        lines.append("OBJECTS TO MIGRATE:")
        lines.append(f"{'KEY':<40} {'SIZE':>12} {'LAST MODIFIED':<20}")
        lines.append("-" * 60)

        for obj in objects[:50]:
            key = obj.get("Key", "")[:38] if len(obj.get("Key", "")) > 38 else obj.get("Key", "")
            size = ReportGenerator.format_size(obj.get("Size", 0))
            last_modified = obj.get("LastModified", "")[:19] if obj.get("LastModified") else ""
            lines.append(f"{key:<40} {size:>12} {last_modified:<20}")

        if len(objects) > 50:
            lines.append(f"... and {len(objects) - 50} more objects")

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

        total_size = sum(obj.get("Size", 0) for obj in objects)

        lines = []
        lines.append("=" * 60)
        lines.append("        SYNC PREVIEW")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Source:      {source_bucket}")
        lines.append(f"Target:      {target_bucket}")
        if since:
            lines.append(f"Since:       {since}")
        lines.append("")
        lines.append("STATISTICS:")
        lines.append(f"  Objects to Sync: {len(objects):,}")
        lines.append(f"  Total Size:      {ReportGenerator.format_size(total_size)}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)
