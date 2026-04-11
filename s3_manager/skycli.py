#!/usr/bin/env python3
import sys
import argparse
from typing import Optional

from .skyconfig import config
from .skyclient import SkyClient
from .skymetadata import SkyMetadata
from .skyacl import SkyACL
from .skysync import create_sync, get_sync, get_sync_history
from .skyvalidate import create_validation, get_validation_report, list_validation_reports
from .skyreport import ReportGenerator


def get_client(config_name: str, profile: Optional[str] = None) -> SkyClient:
    cfg = config.get_profile(config_name, profile)
    if not cfg:
        raise ValueError(f"Config '{config_name}' not found")
    return SkyClient(
        endpoint=cfg["endpoint"],
        access_key=cfg["access_key"],
        secret_key=cfg["secret_key"],
        region=cfg.get("region", "us-east-1"),
        use_path_style=cfg.get("use_path_style", False),
        verify_ssl=cfg.get("verify_ssl", True)
    )


def cmd_config_add(args):
    config.add_profile(
        name=args.name,
        endpoint=args.endpoint,
        access_key=args.access_key,
        secret_key=args.secret_key,
        region=args.region or "us-east-1",
        use_path_style=args.use_path_style,
        verify_ssl=not args.no_verify_ssl,
        profile=args.profile
    )
    print(f"Config '{args.name}' added successfully")


def cmd_config_list(args):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import sys
    import time
    
    profiles = config.list_profiles(args.profile)
    if not profiles:
        print("No configs found")
        return

    if not args.test_all:
        print(f"{'NAME':<20} {'ENDPOINT':<40} {'REGION':<15}")
        print("-" * 75)
        for p in sorted(profiles, key=lambda x: x["name"]):
            print(f"{p['name']:<20} {p['endpoint']:<40} {p.get('region', '-'):<15}")
        print(f"\nTip: Use --test-all to test connection status")
        return

    print(f"{'NAME':<20} {'ENDPOINT':<40} {'REGION':<15} STATUS")
    print("-" * 80)
    
    results = []
    completed = 0
    total = len(profiles)
    
    def test_single_config(cfg):
        try:
            result = config.test_connection(cfg["name"], args.profile)
            return cfg["name"], cfg["endpoint"], cfg.get("region", "-"), result.get("success", False), result.get("error", "")
        except Exception as e:
            return cfg["name"], cfg["endpoint"], cfg.get("region", "-"), False, str(e)
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(test_single_config, p) for p in profiles]
        
        for future in as_completed(futures):
            completed += 1
            sys.stdout.write(f"\rTesting connections: {completed}/{total}...")
            sys.stdout.flush()
            
            try:
                results.append(future.result(timeout=10))
            except Exception as e:
                results.append(("unknown", "unknown", "-", False, str(e)))
    
    sys.stdout.write("\r" + " " * 50 + "\r")
    sys.stdout.flush()
    
    for name, endpoint, region, success, error in sorted(results):
        if success:
            status = '✓ 成功'
        elif error and "Connection" in error:
            status = '✗ 连接失败'
        elif error:
            status = f'✗ 错误'
        else:
            status = '✗ 失败'
        print(f"{name:<20} {endpoint:<40} {region:<15} {status}")


def cmd_config_test(args):
    result = config.test_connection(args.name, args.profile)
    if result.get("success"):
        print(f"✓ Connection successful")
        print(f"  Region: {result.get('region', 'N/A')}")
        print(f"  Bucket count: {result.get('bucket_count', 0)}")
    else:
        print(f"✗ Connection failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)


def cmd_config_rm(args):
    if config.rm_profile(args.name, args.profile):
        print(f"Config '{args.name}' removed")
    else:
        print(f"Config '{args.name}' not found")
        sys.exit(1)


def cmd_bucket_list(args):
    client = get_client(args.source, args.profile)
    buckets = client.list_buckets()

    if args.output == "json":
        import json
        print(json.dumps(buckets, indent=2))
    else:
        print(f"{'BUCKET NAME':<40} {'CREATION DATE':<20} OBJECTS")
        print("-" * 80)
        for b in buckets:
            print(f"{b['Name']:<40} {b.get('CreationDate', '')[:19]:<20}")


def cmd_bucket_info(args):
    client = get_client(args.source, args.profile)
    location = client.get_bucket_location(args.bucket)
    versioning = client.get_bucket_versioning(args.bucket)
    policy = client.get_bucket_policy(args.bucket)

    print(f"Bucket: {args.bucket}")
    print(f"Region: {location}")
    print(f"Versioning: {versioning}")
    if policy:
        print(f"Policy: Configured")


def cmd_bucket_create(args):
    client = get_client(args.source, args.profile)
    client.create_bucket(args.bucket, args.region)
    print(f"Bucket '{args.bucket}' created")


def cmd_bucket_rm(args):
    client = get_client(args.source, args.profile)
    if not args.force:
        response = input(f"Delete bucket '{args.bucket}'? (yes/no): ")
        if response.lower() != "yes":
            print("Cancelled")
            return
    client.delete_bucket(args.bucket)
    print(f"Bucket '{args.bucket}' deleted")


def cmd_object_list(args):
    client = get_client(args.source, args.profile)
    result = client.list_objects(args.bucket, args.prefix, args.delimiter, args.max_keys)

    if args.output == "json":
        import json
        print(json.dumps(result, indent=2))
    else:
        print(f"{'KEY':<50} {'LAST MODIFIED':<20} {'SIZE':>12}")
        print("-" * 90)
        for obj in result.get("objects", []):
            key = obj["Key"][:48] if len(obj["Key"]) > 48 else obj["Key"]
            last_mod = obj.get("LastModified", "")[:19] if obj.get("LastModified") else ""
            size = ReportGenerator.format_size(obj.get("Size", 0))
            print(f"{key:<50} {last_mod:<20} {size:>12}")


def cmd_object_put(args):
    client = get_client(args.source, args.profile)

    with open(args.file, "rb") as f:
        body = f.read()

    metadata = {}
    if args.metadata:
        for m in args.metadata:
            if "=" in m:
                k, v = m.split("=", 1)
                metadata[k] = v

    result = client.put_object(
        bucket=args.bucket,
        key=args.key,
        body=body,
        metadata=metadata if metadata else None,
        content_type=args.content_type,
        storage_class=args.storage_class or "STANDARD",
        acl=args.acl
    )
    print(f"Object '{args.key}' uploaded, ETag: {result.get('ETag')}")


def cmd_object_get(args):
    client = get_client(args.source, args.profile)
    response = client.get_object(args.bucket, args.key)

    with open(args.file, "wb") as f:
        f.write(response["Body"].read())

    print(f"Object '{args.key}' downloaded to '{args.file}'")


def cmd_object_rm(args):
    client = get_client(args.source, args.profile)
    client.delete_object(args.bucket, args.key, args.version_id)
    print(f"Object '{args.key}' deleted")


def cmd_object_info(args):
    client = get_client(args.source, args.profile)
    info = client.head_object(args.bucket, args.key, args.version_id)

    if args.output == "json":
        import json
        print(json.dumps(info, indent=2))
    else:
        print(f"Object: {args.key}")
        print(f"Bucket: {args.bucket}")
        print(f"Size: {ReportGenerator.format_size(info.get('ContentLength', 0))}")
        print(f"Last Modified: {info.get('LastModified', 'N/A')}")
        print(f"ETag: {info.get('ETag', 'N/A')}")
        print(f"Storage Class: {info.get('StorageClass', 'STANDARD')}")

        if info.get("Metadata"):
            print("\nMetadata:")
            for k, v in info["Metadata"].items():
                print(f"  {k}: {v}")

        if args.include_acl:
            acl = client.get_object_acl(args.bucket, args.key, args.version_id)
            print("\nACL:")
            print(SkyACL(client).format_acl(acl))


def cmd_object_cp(args):
    source_client = get_client(args.source, args.profile)
    target_client = get_client(args.target, args.profile)

    if args.preserve_metadata:
        metadata_handler = SkyMetadata(source_client)
        source_info = source_client.head_object(args.source_bucket, args.source_key)
        metadata = source_info.get("Metadata", {})
        content_type = source_info.get("ContentType")
    else:
        metadata = None
        content_type = None

    result = target_client.copy_object(
        source_bucket=args.source_bucket,
        source_key=args.source_key,
        target_bucket=args.target_bucket,
        target_key=args.target_key,
        metadata=metadata,
        metadata_directive="COPY" if args.preserve_metadata else "REPLACE",
        content_type=content_type
    )

    if args.preserve_acl:
        acl_handler = SkyACL(source_client)
        acl_handler.copy(args.source_bucket, args.source_key, args.target_bucket, args.target_key)

    print(f"Object copied, ETag: {result.get('ETag')}")


def cmd_metadata_get(args):
    client = get_client(args.source, args.profile)
    metadata_handler = SkyMetadata(client)
    meta = metadata_handler.get(args.bucket, args.key)

    if args.output == "json":
        import json
        print(json.dumps(meta, indent=2))
    else:
        print(f"Metadata for '{args.key}':")
        for k, v in meta.items():
            print(f"  {k}: {v}")


def cmd_metadata_set(args):
    client = get_client(args.source, args.profile)
    metadata_handler = SkyMetadata(client)

    metadata = {}
    for m in args.metadata:
        if "=" in m:
            k, v = m.split("=", 1)
            metadata[k] = v

    metadata_handler.set(args.bucket, args.key, metadata, args.operation)
    print(f"Metadata updated for '{args.key}'")


def cmd_acl_get(args):
    client = get_client(args.source, args.profile)
    acl_handler = SkyACL(client)
    acl = acl_handler.get(args.bucket, args.key)

    if args.output == "json":
        import json
        print(json.dumps(acl, indent=2))
    else:
        print(SkyACL(client).format_acl(acl))


def cmd_acl_set(args):
    client = get_client(args.source, args.profile)
    acl_handler = SkyACL(client)

    acl_handler.set(
        bucket=args.bucket,
        key=args.key,
        acl=args.acl,
        grant_read=args.grant_read,
        grant_full_control=args.grant_full_control
    )
    print(f"ACL set for '{args.key}'")


def cmd_acl_cp(args):
    source_client = get_client(args.source, args.profile)
    acl_handler = SkyACL(source_client)
    acl_handler.copy(args.source_bucket, args.source_key, args.target_bucket, args.target_key)
    print(f"ACL copied from '{args.source_key}' to '{args.target_key}'")


def cmd_migrate_run(args):
    print(f"Starting migration...")

    migration = create_migration(
        source_config_name=args.source,
        source_bucket=args.source_bucket,
        target_config_name=args.target,
        target_bucket=args.target_bucket,
        source_prefix=args.source_prefix or "",
        target_prefix=args.target_prefix or "",
        threads=args.threads,
        storage_class=args.storage_class,
        preserve_metadata=args.preserve_metadata,
        preserve_acl=args.preserve_acl,
        exclude_patterns=args.exclude,
        include_patterns=args.include,
        profile=args.profile
    )

    def progress_callback(progress):
        pct = (progress["processed"] / progress["total"]) * 100 if progress["total"] > 0 else 0
        print(f"\rProgress: {progress['processed']}/{progress['total']} ({pct:.1f}%) Failed: {progress['failed']}", end="", flush=True)

    result = migration.run(progress_callback if not args.quiet else None, args.resume)
    print()

    print(ReportGenerator.generate_migration_report(result, args.output))


def cmd_migrate_list(args):
    history = get_sync_history()
    if not history:
        print("No sync history found")
        return

    for m in history[:args.limit]:
        print(f"{m.get('sync_id')}: {m.get('status')} - {m.get('source_bucket')} -> {m.get('target_bucket')}")


def cmd_migrate_status(args):
    sync = get_sync(args.migration_id)
    if not sync:
        print(f"Sync '{args.migration_id}' not found")
        sys.exit(1)

    import json
    print(json.dumps(sync, indent=2))


def cmd_sync_run(args):
    from datetime import datetime
    from .skysync import create_sync

    since = None
    if args.since:
        since = datetime.fromisoformat(args.since.replace("Z", "+00:00"))

    mode = "sync" if (since or args.since_last_sync or args.delete) else "migration"

    if args.dry_run:
        source_client = get_client(args.source, args.profile)
        target_client = get_client(args.target, args.profile)

        source_objects = list(source_client.list_objects_all(args.source_bucket, args.source_prefix or ""))
        target_objects = {}
        for obj in target_client.list_objects_all(args.target_bucket, args.target_prefix or ""):
            key_without_prefix = obj["Key"][len(args.target_prefix or ""):] if args.target_prefix else obj["Key"]
            target_objects[key_without_prefix] = obj

        print(f"Dry run - {mode} simulation")
        print(f"Source: {args.source}/{args.source_bucket}/{args.source_prefix or ''}")
        print(f"Target: {args.target}/{args.target_bucket}/{args.target_prefix or ''}")
        print()

        will_upload = []
        will_delete = []
        will_skip = []

        for obj in source_objects:
            source_key = obj["Key"]
            key_without_prefix = source_key[len(args.source_prefix or ""):] if args.source_prefix else source_key
            target_key = (args.target_prefix or "") + key_without_prefix

            if key_without_prefix not in target_objects:
                will_upload.append(source_key)
            else:
                source_etag = obj.get("ETag", "").strip('"')
                target_obj = target_objects[key_without_prefix]
                target_etag = target_obj.get("ETag", "").strip('"')

                if source_etag != target_etag or obj.get("Size", 0) != target_obj.get("Size", 0):
                    will_upload.append(source_key)
                else:
                    will_skip.append(source_key)

        if args.delete:
            for target_key, target_obj in target_objects.items():
                if target_key not in [obj["Key"][len(args.source_prefix or ""):] for obj in source_objects]:
                    will_delete.append(target_obj["Key"])

        print(f"Objects to upload: {len(will_upload)}")
        print(f"Objects to delete: {len(will_delete)}")
        print(f"Objects to skip: {len(will_skip)}")
        print()

        if will_upload:
            print("--- Upload list (first 10) ---")
            for key in will_upload[:10]:
                print(f"  [UPLOAD] {key}")
            if len(will_upload) > 10:
                print(f"  ... and {len(will_upload) - 10} more")
            print()

        if will_delete:
            print("--- Delete list (first 10) ---")
            for key in will_delete[:10]:
                print(f"  [DELETE] {key}")
            if len(will_delete) > 10:
                print(f"  ... and {len(will_delete) - 10} more")
            print()

        if will_skip:
            print("--- Skip list (first 10) ---")
            for key in will_skip[:10]:
                print(f"  [SKIP] {key}")
            if len(will_skip) > 10:
                print(f"  ... and {len(will_skip) - 10} more")
            print()

        print("Dry run completed. No changes were made.")
        return

    print(f"Starting {mode}...")

    sync_task = create_sync(
        source_config_name=args.source,
        source_bucket=args.source_bucket,
        target_config_name=args.target,
        target_bucket=args.target_bucket,
        source_prefix=args.source_prefix or "",
        target_prefix=args.target_prefix or "",
        since=since,
        since_last_sync=args.since_last_sync,
        delete=args.delete,
        threads=args.threads,
        part_size=args.part_size,
        storage_class=args.storage_class,
        preserve_metadata=args.preserve_metadata,
        preserve_acl=args.preserve_acl,
        exclude_patterns=args.exclude,
        include_patterns=args.include,
        profile=args.profile
    )

    def progress_callback(progress):
        pct = (progress["processed"] / progress["total"]) * 100 if progress["total"] > 0 else 0
        print(f"\rProgress: {progress['processed']}/{progress['total']} ({pct:.1f}%) Uploaded: {progress['uploaded']}, Deleted: {progress['deleted']}, Skipped: {progress['skipped']}, Failed: {progress['failed']}", end="", flush=True)

    result = sync_task.run(progress_callback if not args.quiet else None, args.resume)
    print()

    print(ReportGenerator.generate_migration_report(result, args.output))


def cmd_sync_list(args):
    history = get_sync_history()
    if not history:
        print("No sync history found")
        return

    for s in history[:args.limit]:
        print(f"{s.get('sync_id')}: {s.get('status')} - {s.get('source_bucket')} -> {s.get('target_bucket')}")


def cmd_validate_run(args):
    check_content = args.check in ["content", "all"]
    check_metadata = args.check in ["metadata", "all"]
    check_acl = args.check in ["acl", "all"]

    validation = create_validation(
        source_config_name=args.source,
        source_bucket=args.source_bucket,
        target_config_name=args.target,
        target_bucket=args.target_bucket,
        prefix=args.prefix or "",
        check_content=check_content,
        check_metadata=check_metadata,
        check_acl=check_acl,
        metadata_fields=args.fields.split(",") if args.fields else None,
        threads=args.threads,
        profile=args.profile
    )

    def progress_callback(progress):
        print(f"\rValidating: {progress['processed']}/{progress['total']}, failed={progress['failed']}", end="", flush=True)

    result = validation.run(progress_callback if not args.quiet else None)
    print()

    print(ReportGenerator.generate_validation_report(result, args.output))


def cmd_validate_report(args):
    report = get_validation_report(args.validation_id)
    if not report:
        print(f"Report '{args.validation_id}' not found")
        sys.exit(1)

    print(ReportGenerator.generate_validation_report(report, args.output))


def cmd_validate_list(args):
    reports = list_validation_reports()
    if not reports:
        print("No validation reports found")
        return

    for r in reports[:args.limit]:
        print(f"{r.get('validation_id')}: {r.get('timestamp')} - {r.get('status')}")


def main():
    parser = argparse.ArgumentParser(prog="skycli", description="S3 Compatible Object Storage Manager")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    profile_parser = argparse.ArgumentParser(add_help=False)
    profile_parser.add_argument("--profile", help="Config profile name")

    output_parser = argparse.ArgumentParser(add_help=False)
    output_parser.add_argument("--output", choices=["json", "table"], default="table", help="Output format")

    quiet_parser = argparse.ArgumentParser(add_help=False)
    quiet_parser.add_argument("--quiet", action="store_true", help="Quiet mode")

    config_parser = subparsers.add_parser("config", help="Config management")
    config_subparsers = config_parser.add_subparsers(dest="config_command")

    c_add = config_subparsers.add_parser("add", help="Add config")
    c_add.add_argument("--name", required=True, help="Config name")
    c_add.add_argument("--endpoint", required=True, help="S3 endpoint URL")
    c_add.add_argument("--access-key", required=True, help="Access key")
    c_add.add_argument("--secret-key", required=True, help="Secret key")
    c_add.add_argument("--region", help="Region")
    c_add.add_argument("--use-path-style", action="store_true", help="Use path style")
    c_add.add_argument("--no-verify-ssl", action="store_true", help="Disable SSL verification")
    c_add.add_argument("--profile", help="Profile name")
    c_add.set_defaults(func=cmd_config_add)

    c_list = config_subparsers.add_parser("list", help="List configs")
    c_list.add_argument("--profile", help="Profile name")
    c_list.add_argument("--test-all", action="store_true", help="Test all connections (slower)")
    c_list.set_defaults(func=cmd_config_list)

    c_test = config_subparsers.add_parser("test", help="Test connection")
    c_test.add_argument("--name", required=True, help="Config name")
    c_test.add_argument("--profile", help="Profile name")
    c_test.set_defaults(func=cmd_config_test)

    c_rm = config_subparsers.add_parser("rm", help="Remove config")
    c_rm.add_argument("--name", required=True, help="Config name")
    c_rm.add_argument("--profile", help="Profile name")
    c_rm.set_defaults(func=cmd_config_rm)

    bucket_parser = subparsers.add_parser("bucket", help="Bucket operations")
    bucket_subparsers = bucket_parser.add_subparsers(dest="bucket_command")

    b_list = bucket_subparsers.add_parser("list", help="List buckets")
    b_list.add_argument("--source", required=True, help="Config name")
    b_list.add_argument("--profile", help="Profile name")
    b_list.add_argument("--output", choices=["json", "table"], default="table")
    b_list.set_defaults(func=cmd_bucket_list)

    b_info = bucket_subparsers.add_parser("info", help="Bucket info")
    b_info.add_argument("--source", required=True, help="Config name")
    b_info.add_argument("--bucket", required=True, help="Bucket name")
    b_info.add_argument("--profile", help="Profile name")
    b_info.set_defaults(func=cmd_bucket_info)

    b_create = bucket_subparsers.add_parser("create", help="Create bucket")
    b_create.add_argument("--source", required=True, help="Config name")
    b_create.add_argument("--bucket", required=True, help="Bucket name")
    b_create.add_argument("--region", help="Region")
    b_create.add_argument("--profile", help="Profile name")
    b_create.set_defaults(func=cmd_bucket_create)

    b_rm = bucket_subparsers.add_parser("rm", help="Delete bucket")
    b_rm.add_argument("--source", required=True, help="Config name")
    b_rm.add_argument("--bucket", required=True, help="Bucket name")
    b_rm.add_argument("--force", action="store_true", help="Force delete")
    b_rm.add_argument("--profile", help="Profile name")
    b_rm.set_defaults(func=cmd_bucket_rm)

    object_parser = subparsers.add_parser("object", help="Object operations")
    object_subparsers = object_parser.add_subparsers(dest="object_command")

    o_list = object_subparsers.add_parser("list", help="List objects")
    o_list.add_argument("--source", required=True, help="Config name")
    o_list.add_argument("--bucket", required=True, help="Bucket name")
    o_list.add_argument("--prefix", default="", help="Prefix filter")
    o_list.add_argument("--delimiter", help="Delimiter")
    o_list.add_argument("--max-keys", type=int, default=1000, help="Max keys")
    o_list.add_argument("--profile", help="Profile name")
    o_list.add_argument("--output", choices=["json", "table"], default="table")
    o_list.set_defaults(func=cmd_object_list)

    o_put = object_subparsers.add_parser("put", help="Upload object")
    o_put.add_argument("--source", required=True, help="Config name")
    o_put.add_argument("--bucket", required=True, help="Bucket name")
    o_put.add_argument("--key", required=True, help="Object key")
    o_put.add_argument("--file", required=True, help="Local file path")
    o_put.add_argument("--content-type", help="Content type")
    o_put.add_argument("--metadata", nargs="+", help="Metadata key=value")
    o_put.add_argument("--storage-class", help="Storage class")
    o_put.add_argument("--acl", help="ACL")
    o_put.add_argument("--profile", help="Profile name")
    o_put.set_defaults(func=cmd_object_put)

    o_get = object_subparsers.add_parser("get", help="Download object")
    o_get.add_argument("--source", required=True, help="Config name")
    o_get.add_argument("--bucket", required=True, help="Bucket name")
    o_get.add_argument("--key", required=True, help="Object key")
    o_get.add_argument("--file", required=True, help="Local file path")
    o_get.add_argument("--profile", help="Profile name")
    o_get.set_defaults(func=cmd_object_get)

    o_rm = object_subparsers.add_parser("rm", help="Delete object")
    o_rm.add_argument("--source", required=True, help="Config name")
    o_rm.add_argument("--bucket", required=True, help="Bucket name")
    o_rm.add_argument("--key", required=True, help="Object key")
    o_rm.add_argument("--version-id", help="Version ID")
    o_rm.add_argument("--profile", help="Profile name")
    o_rm.set_defaults(func=cmd_object_rm)

    o_info = object_subparsers.add_parser("info", help="Object info")
    o_info.add_argument("--source", required=True, help="Config name")
    o_info.add_argument("--bucket", required=True, help="Bucket name")
    o_info.add_argument("--key", required=True, help="Object key")
    o_info.add_argument("--version-id", help="Version ID")
    o_info.add_argument("--include-metadata", action="store_true", help="Include metadata")
    o_info.add_argument("--include-acl", action="store_true", help="Include ACL")
    o_info.add_argument("--profile", help="Profile name")
    o_info.add_argument("--output", choices=["json", "table"], default="table")
    o_info.set_defaults(func=cmd_object_info)

    o_cp = object_subparsers.add_parser("cp", help="Copy object")
    o_cp.add_argument("--source", required=True, help="Source config name")
    o_cp.add_argument("--source-bucket", required=True, help="Source bucket")
    o_cp.add_argument("--source-key", required=True, help="Source key")
    o_cp.add_argument("--target", required=True, help="Target config name")
    o_cp.add_argument("--target-bucket", required=True, help="Target bucket")
    o_cp.add_argument("--target-key", required=True, help="Target key")
    o_cp.add_argument("--preserve-metadata", action="store_true", help="Preserve metadata")
    o_cp.add_argument("--preserve-acl", action="store_true", help="Preserve ACL")
    o_cp.add_argument("--profile", help="Profile name")
    o_cp.set_defaults(func=cmd_object_cp)

    metadata_parser = subparsers.add_parser("metadata", help="Metadata operations")
    metadata_subparsers = metadata_parser.add_subparsers(dest="metadata_command")

    m_get = metadata_subparsers.add_parser("get", help="Get metadata")
    m_get.add_argument("--source", required=True, help="Config name")
    m_get.add_argument("--bucket", required=True, help="Bucket name")
    m_get.add_argument("--key", required=True, help="Object key")
    m_get.add_argument("--profile", help="Profile name")
    m_get.add_argument("--output", choices=["json", "table"], default="table")
    m_get.set_defaults(func=cmd_metadata_get)

    m_set = metadata_subparsers.add_parser("set", help="Set metadata")
    m_set.add_argument("--source", required=True, help="Config name")
    m_set.add_argument("--bucket", required=True, help="Bucket name")
    m_set.add_argument("--key", required=True, help="Object key")
    m_set.add_argument("--metadata", nargs="+", required=True, help="Metadata key=value")
    m_set.add_argument("--operation", choices=["COPY", "REPLACE"], default="REPLACE")
    m_set.add_argument("--profile", help="Profile name")
    m_set.set_defaults(func=cmd_metadata_set)

    acl_parser = subparsers.add_parser("acl", help="ACL operations")
    acl_subparsers = acl_parser.add_subparsers(dest="acl_command")

    a_get = acl_subparsers.add_parser("get", help="Get ACL")
    a_get.add_argument("--source", required=True, help="Config name")
    a_get.add_argument("--bucket", required=True, help="Bucket name")
    a_get.add_argument("--key", help="Object key")
    a_get.add_argument("--profile", help="Profile name")
    a_get.add_argument("--output", choices=["json", "table"], default="table")
    a_get.set_defaults(func=cmd_acl_get)

    a_set = acl_subparsers.add_parser("set", help="Set ACL")
    a_set.add_argument("--source", required=True, help="Config name")
    a_set.add_argument("--bucket", required=True, help="Bucket name")
    a_set.add_argument("--key", help="Object key")
    a_set.add_argument("--acl", help="Canned ACL")
    a_set.add_argument("--grant-read", action="store_true", help="Grant read")
    a_set.add_argument("--grant-full-control", action="store_true", help="Grant full control")
    a_set.add_argument("--profile", help="Profile name")
    a_set.set_defaults(func=cmd_acl_set)

    a_cp = acl_subparsers.add_parser("cp", help="Copy ACL")
    a_cp.add_argument("--source", required=True, help="Source config name")
    a_cp.add_argument("--source-bucket", required=True, help="Source bucket")
    a_cp.add_argument("--source-key", required=True, help="Source key")
    a_cp.add_argument("--target", required=True, help="Target config name")
    a_cp.add_argument("--target-bucket", required=True, help="Target bucket")
    a_cp.add_argument("--target-key", required=True, help="Target key")
    a_cp.add_argument("--profile", help="Profile name")
    a_cp.set_defaults(func=cmd_acl_cp)

    sync_parser = subparsers.add_parser("sync", help="Sync/Migration operations")
    sync_subparsers = sync_parser.add_subparsers(dest="sync_command")

    s_run = sync_subparsers.add_parser("run", help="Run sync/migration")
    s_run.add_argument("--source", required=True, help="Source config name")
    s_run.add_argument("--source-bucket", required=True, help="Source bucket")
    s_run.add_argument("--source-prefix", help="Source prefix")
    s_run.add_argument("--target", required=True, help="Target config name")
    s_run.add_argument("--target-bucket", required=True, help="Target bucket")
    s_run.add_argument("--target-prefix", help="Target prefix")
    s_run.add_argument("--since", help="Sync since (ISO format)")
    s_run.add_argument("--since-last-sync", action="store_true", help="Sync since last sync")
    s_run.add_argument("--delete", action="store_true", help="Delete objects not in source (sync mode)")
    s_run.add_argument("--threads", type=int, default=10, help="Threads")
    s_run.add_argument("--part-size", type=int, default=8, help="Part size (MB)")
    s_run.add_argument("--storage-class", help="Storage class")
    s_run.add_argument("--preserve-metadata", action="store_true", default=True, help="Preserve metadata")
    s_run.add_argument("--preserve-acl", action="store_true", default=True, help="Preserve ACL")
    s_run.add_argument("--exclude", nargs="+", help="Exclude patterns")
    s_run.add_argument("--include", nargs="+", help="Include patterns")
    s_run.add_argument("--dry-run", action="store_true", help="Dry run")
    s_run.add_argument("--resume", action="store_true", help="Resume migration")
    s_run.add_argument("--profile", help="Profile name")
    s_run.add_argument("--output", choices=["json", "table"], default="table")
    s_run.add_argument("--quiet", action="store_true", help="Quiet mode")
    s_run.set_defaults(func=cmd_sync_run)

    s_list = sync_subparsers.add_parser("list", help="List sync/migration history")
    s_list.add_argument("--limit", type=int, default=10, help="Limit")
    s_list.set_defaults(func=cmd_sync_list)

    s_status = sync_subparsers.add_parser("status", help="Sync/migration status")
    s_status.add_argument("--migration-id", required=True, help="Migration ID")
    s_status.set_defaults(func=cmd_migrate_status)

    validate_parser = subparsers.add_parser("validate", help="Validation operations")
    validate_subparsers = validate_parser.add_subparsers(dest="validate_command")

    v_run = validate_subparsers.add_parser("run", help="Run validation")
    v_run.add_argument("--source", required=True, help="Source config name")
    v_run.add_argument("--source-bucket", required=True, help="Source bucket")
    v_run.add_argument("--target", required=True, help="Target config name")
    v_run.add_argument("--target-bucket", required=True, help="Target bucket")
    v_run.add_argument("--prefix", help="Prefix filter")
    v_run.add_argument("--check", choices=["content", "metadata", "acl", "all"], default="all", help="What to check")
    v_run.add_argument("--fields", help="Metadata fields to check (comma-separated)")
    v_run.add_argument("--threads", type=int, default=10, help="Threads")
    v_run.add_argument("--profile", help="Profile name")
    v_run.add_argument("--output", choices=["json", "table"], default="table")
    v_run.add_argument("--quiet", action="store_true", help="Quiet mode")
    v_run.set_defaults(func=cmd_validate_run)

    v_report = validate_subparsers.add_parser("report", help="Show validation report")
    v_report.add_argument("--validation-id", required=True, help="Validation ID")
    v_report.add_argument("--output", choices=["json", "table"], default="table")
    v_report.set_defaults(func=cmd_validate_report)

    v_list = validate_subparsers.add_parser("list", help="List validation reports")
    v_list.add_argument("--limit", type=int, default=10, help="Limit")
    v_list.set_defaults(func=cmd_validate_list)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if hasattr(args, "func"):
        try:
            args.func(args)
        except Exception as e:
            print(f"Error: {e}")
            if hasattr(args, "debug") and args.debug:
                import traceback
                traceback.print_exc()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
