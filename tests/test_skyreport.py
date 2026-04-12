import pytest
import json
from s3_manager.skyreport import ReportGenerator


class TestFormatSize:
    def test_bytes(self):
        assert ReportGenerator.format_size(0) == "0.00 B"
        assert ReportGenerator.format_size(500) == "500.00 B"
        assert ReportGenerator.format_size(1023) == "1023.00 B"

    def test_kilobytes(self):
        assert ReportGenerator.format_size(1024) == "1.00 KB"
        assert ReportGenerator.format_size(1536) == "1.50 KB"
        assert ReportGenerator.format_size(10240) == "10.00 KB"

    def test_megabytes(self):
        assert ReportGenerator.format_size(1048576) == "1.00 MB"
        assert ReportGenerator.format_size(5242880) == "5.00 MB"
        assert ReportGenerator.format_size(10485760) == "10.00 MB"

    def test_gigabytes(self):
        assert ReportGenerator.format_size(1073741824) == "1.00 GB"
        assert ReportGenerator.format_size(5368709120) == "5.00 GB"

    def test_terabytes(self):
        assert ReportGenerator.format_size(1099511627776) == "1.00 TB"

    def test_petabytes(self):
        result = ReportGenerator.format_size(1099511627776 * 1024)
        assert "PB" in result
        assert float(result.split()[0]) >= 1.0


class TestFormatDuration:
    def test_seconds(self):
        assert ReportGenerator.format_duration(0) == "0.0s"
        assert ReportGenerator.format_duration(30) == "30.0s"
        assert ReportGenerator.format_duration(59.9) == "59.9s"

    def test_minutes(self):
        assert ReportGenerator.format_duration(60) == "1.0m"
        assert ReportGenerator.format_duration(120) == "2.0m"
        assert ReportGenerator.format_duration(180) == "3.0m"

    def test_hours(self):
        assert ReportGenerator.format_duration(3600) == "1.0h"
        assert ReportGenerator.format_duration(7200) == "2.0h"
        assert ReportGenerator.format_duration(86400) == "24.0h"


class TestGenerateMigrationReport:
    def test_migration_report_table_format(self):
        summary = {
            "migration_id": "test-mig-001",
            "status": "completed",
            "start_time": "2024-01-01T10:00:00",
            "end_time": "2024-01-01T10:30:00",
            "duration_seconds": 1800,
            "source_bucket": "source-bucket",
            "source_prefix": "prefix/",
            "target_bucket": "target-bucket",
            "target_prefix": "prefix/",
            "total_objects": 100,
            "processed_objects": 95,
            "failed_objects": 5,
            "total_bytes": 104857600,
            "transferred_bytes": 99614720,
            "failed_list": [
                {"key": "file1.txt", "error": "Connection timeout"},
                {"key": "file2.txt", "error": "Access denied"}
            ]
        }

        report = ReportGenerator.generate_migration_report(summary, "table")

        assert "迁 移 报 告" in report
        assert "test-mig-001" in report
        assert "COMPLETED" in report
        assert "source-bucket" in report
        assert "target-bucket" in report
        assert "95" in report
        assert "5" in report
        assert "file1.txt" in report
        assert "Connection timeout" in report

    def test_migration_report_json_format(self):
        summary = {
            "migration_id": "test-mig-001",
            "status": "completed",
            "total_objects": 100
        }

        report = ReportGenerator.generate_migration_report(summary, "json")

        parsed = json.loads(report)
        assert parsed["migration_id"] == "test-mig-001"
        assert parsed["status"] == "completed"
        assert parsed["total_objects"] == 100

    def test_migration_report_missing_fields(self):
        summary = {}

        report = ReportGenerator.generate_migration_report(summary, "table")

        assert "N/A" in report
        assert "0" in report

    def test_migration_report_empty_failed_list(self):
        summary = {
            "migration_id": "test-mig-001",
            "failed_list": []
        }

        report = ReportGenerator.generate_migration_report(summary, "table")

        assert "FAILED OBJECTS" not in report


class TestGenerateSyncReport:
    def test_sync_report_table_format(self):
        summary = {
            "sync_id": "sync-001",
            "status": "completed",
            "start_time": "2024-01-01T10:00:00",
            "end_time": "2024-01-01T10:30:00",
            "duration_seconds": 1800,
            "source_bucket": "source-bucket",
            "source_prefix": "prefix/",
            "target_bucket": "target-bucket",
            "target_prefix": "prefix/",
            "total_objects": 50,
            "uploaded": 45,
            "deleted": 2,
            "skipped": 1,
            "failed": 2
        }

        report = ReportGenerator.generate_sync_report(summary, "table")

        assert "同 步 报 告" in report
        assert "sync-001" in report
        assert "COMPLETED" in report
        assert "50" in report
        assert "45" in report
        assert "2" in report

    def test_sync_report_json_format(self):
        summary = {
            "sync_id": "sync-001",
            "status": "completed",
            "total_objects": 50
        }

        report = ReportGenerator.generate_sync_report(summary, "json")

        parsed = json.loads(report)
        assert parsed["sync_id"] == "sync-001"

    def test_sync_report_missing_fields(self):
        summary = {}

        report = ReportGenerator.generate_sync_report(summary, "table")

        assert "N/A" in report


class TestGenerateValidationReport:
    def test_validation_report_table_format(self):
        report = {
            "validation_id": "val-001",
            "timestamp": "2024-01-01T10:00:00",
            "status": "completed",
            "duration_seconds": 600,
            "source_bucket": "source-bucket",
            "prefix": "prefix/",
            "target_bucket": "target-bucket",
            "summary": {
                "total_objects": 100,
                "content_passed": 95,
                "content_failed": 3,
                "metadata_passed": 98,
                "metadata_failed": 2,
                "acl_passed": 100,
                "acl_failed": 0
            },
            "failed_objects": [
                {"key": "failed1.txt", "errors": ["Content mismatch", "Size differs"]}
            ]
        }

        result = ReportGenerator.generate_validation_report(report, "table")

        assert "验 证 报 告" in result
        assert "val-001" in result
        assert "100" in result
        assert "95" in result
        assert "98" in result
        assert "failed1.txt" in result

    def test_validation_report_json_format(self):
        report = {
            "validation_id": "val-001",
            "summary": {"total_objects": 100}
        }

        result = ReportGenerator.generate_validation_report(report, "json")

        parsed = json.loads(result)
        assert parsed["validation_id"] == "val-001"

    def test_validation_report_empty_failed_objects(self):
        report = {
            "validation_id": "val-001",
            "summary": {"total_objects": 100},
            "failed_objects": []
        }

        result = ReportGenerator.generate_validation_report(report, "table")

        assert "FAILED OBJECTS" not in result


class TestGenerateMigrationPreview:
    def test_migration_preview_table_format(self):
        objects = [
            {"Key": "file1.txt", "Size": 1024, "LastModified": "2024-01-01T10:00:00"},
            {"Key": "file2.txt", "Size": 2048, "LastModified": "2024-01-01T11:00:00"}
        ]

        result = ReportGenerator.generate_migration_preview(
            objects,
            "source-bucket",
            "target-bucket",
            "prefix/"
        )

        assert "迁 移 预 览" in result
        assert "source-bucket" in result
        assert "target-bucket" in result
        assert "2" in result
        assert "file1.txt" in result
        assert "file2.txt" in result

    def test_migration_preview_json_format(self):
        objects = [
            {"Key": "file1.txt", "Size": 1024}
        ]

        result = ReportGenerator.generate_migration_preview(
            objects,
            "source-bucket",
            "target-bucket",
            "prefix/",
            "json"
        )

        parsed = json.loads(result)
        assert parsed["source_bucket"] == "source-bucket"
        assert len(parsed["objects"]) == 1

    def test_migration_preview_empty_prefix(self):
        objects = [{"Key": "file1.txt", "Size": 1024}]

        result = ReportGenerator.generate_migration_preview(
            objects,
            "source-bucket",
            "target-bucket",
            ""
        )

        assert "前缀:" in result and "/" in result

    def test_migration_preview_long_key(self):
        long_key = "a" * 60
        objects = [{"Key": long_key, "Size": 1024, "LastModified": "2024-01-01T10:00:00"}]

        result = ReportGenerator.generate_migration_preview(
            objects,
            "source-bucket",
            "target-bucket",
            ""
        )

        assert long_key[:38] in result or "..." in result

    def test_migration_preview_many_objects(self):
        objects = [{"Key": f"file{i}.txt", "Size": 1024, "LastModified": "2024-01-01T10:00:00"}
                   for i in range(60)]

        result = ReportGenerator.generate_migration_preview(
            objects,
            "source-bucket",
            "target-bucket",
            ""
        )

        assert "还有" in result and "个对象" in result


class TestGenerateSyncPreview:
    def test_sync_preview_table_format(self):
        objects = [
            {"Key": "file1.txt", "Size": 1024},
            {"Key": "file2.txt", "Size": 2048}
        ]

        result = ReportGenerator.generate_sync_preview(
            objects,
            "source-bucket",
            "target-bucket",
            "2024-01-01T00:00:00"
        )

        assert "同 步 预 览" in result
        assert "source-bucket" in result
        assert "target-bucket" in result
        assert "2" in result
        assert "2024-01-01T00:00:00" in result

    def test_sync_preview_json_format(self):
        objects = [{"Key": "file1.txt", "Size": 1024}]

        result = ReportGenerator.generate_sync_preview(
            objects,
            "source-bucket",
            "target-bucket",
            None,
            "json"
        )

        parsed = json.loads(result)
        assert parsed["source_bucket"] == "source-bucket"
        assert parsed["since"] is None

    def test_sync_preview_no_since(self):
        objects = [{"Key": "file1.txt", "Size": 1024}]

        result = ReportGenerator.generate_sync_preview(
            objects,
            "source-bucket",
            "target-bucket",
            None
        )

        assert "Since:" not in result

    def test_sync_preview_empty_objects(self):
        result = ReportGenerator.generate_sync_preview(
            [],
            "source-bucket",
            "target-bucket",
            None
        )

        assert "0" in result
