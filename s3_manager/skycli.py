#!/usr/bin/env python3
import sys
import argparse
from typing import Optional

from . import i18n
_ = i18n._
from .skyconfig import config
from .skyclient import SkyClient
from .skymetadata import SkyMetadata
from .skyacl import SkyACL
from .skysync import create_sync, get_sync, get_sync_history
from .skyvalidate import create_validation, get_validation_report, list_validation_reports
from .skyreport import ReportGenerator
from ._version import __version__


def get_client(config_name: str, profile: Optional[str] = None) -> SkyClient:
    cfg = config.get_profile(config_name, profile)
    if not cfg:
        raise ValueError(_("Config '{name}' not found").format(name=config_name))
    return SkyClient(
        endpoint=cfg["endpoint"],
        access_key=cfg["access_key"],
        secret_key=cfg["secret_key"],
        region=cfg.get("region", "us-east-1"),
        use_path_style=cfg.get("use_path_style", False),
        verify_ssl=cfg.get("verify_ssl", True),
        signature_version=cfg.get("signature_version", "s3v4")
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
        signature_version=args.signature_version,
        profile=args.profile
    )
    print(_("Config '{name}' added successfully").format(name=args.name))


def cmd_config_list(args):
    from concurrent.futures import ThreadPoolExecutor, as_completed

    profiles = config.list_profiles(args.profile)
    if not profiles:
        print(_("No configs found"))
        return

    if not args.test_all:
        print("{:<20} {:<40} {:<15}".format(_("NAME"), _("ENDPOINT"), _("REGION")))
        print("-" * 75)
        for p in sorted(profiles, key=lambda x: x["name"]):
            print("{:<20} {:<40} {:<15}".format(
                p['name'],
                p['endpoint'],
                p.get('region', '-')
            ))
        print("\n" + _("Tip: Use --test-all to test connection status"))
        return

    print("{:<20} {:<40} {:<15} {}".format(
        _("NAME"), _("ENDPOINT"), _("REGION"), _("STATUS")
    ))
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
            sys.stdout.write("\r" + _("Testing: {}/{}...").format(completed, total))
            sys.stdout.flush()

            try:
                results.append(future.result(timeout=10))
            except Exception as e:
                results.append(("unknown", "unknown", "-", False, str(e)))

    sys.stdout.write("\r" + " " * 50 + "\r")
    sys.stdout.flush()

    from .constants import CLI_STATUS_MESSAGES
    for name, endpoint, region, success, error in sorted(results):
        if success:
            status = CLI_STATUS_MESSAGES["success"]
        elif error and "Connection" in error:
            status = CLI_STATUS_MESSAGES["connection_failed"]
        elif error:
            status = CLI_STATUS_MESSAGES["error"]
        else:
            status = CLI_STATUS_MESSAGES["failed"]
        print("{:<20} {:<40} {:<15} {}".format(name, endpoint, region, status))


def cmd_config_test(args):
    result = config.test_connection(args.name, args.profile)
    if result.get("success"):
        print("[OK] " + _("Connection successful"))
        print("  " + _("Region: {region}").format(region=result.get('region', 'N/A')))
        print("  " + _("Bucket count: {count}").format(count=result.get('bucket_count', 0)))
    else:
        print("[FAIL] " + _("Connection failed: {error}").format(error=result.get('error', 'Unknown error')))
        sys.exit(1)


def cmd_config_rm(args):
    if config.rm_profile(args.name, args.profile):
        print(_("Config '{name}' removed").format(name=args.name))
    else:
        print(_("Config '{name}' not found").format(name=args.name))
        sys.exit(1)


def cmd_bucket_list(args):
    client = get_client(args.source, args.profile)
    buckets = client.list_buckets()

    if args.output == "json":
        import json
        print(json.dumps(buckets, indent=2))
    else:
        print("{:<40} {:<20} {}".format(_("BUCKET NAME"), _("CREATION DATE"), _("OBJECTS")))
        print("-" * 80)
        for b in buckets:
            print("{:<40} {:<20}".format(
                b['Name'],
                b.get('CreationDate', '')[:19]
            ))


def cmd_bucket_info(args):
    client = get_client(args.source, args.profile)
    location = client.get_bucket_location(args.bucket)
    versioning = client.get_bucket_versioning(args.bucket)
    policy = client.get_bucket_policy(args.bucket)

    print(_("Bucket: {bucket}").format(bucket=args.bucket))
    print(_("Region: {location}").format(location=location))
    print(_("Versioning: {status}").format(status=versioning))
    if policy:
        print(_("Policy: Configured"))


def cmd_bucket_create(args):
    client = get_client(args.source, args.profile)
    client.create_bucket(args.bucket, args.region)
    print(_("Bucket '{bucket}' created").format(bucket=args.bucket))


def cmd_bucket_rm(args):
    client = get_client(args.source, args.profile)
    if not args.force:
        response = input(_("Delete bucket '{bucket}'? (yes/no): ").format(bucket=args.bucket))
        if response.lower() != "yes":
            print(_("Cancelled"))
            return
    client.delete_bucket(args.bucket)
    print(_("Bucket '{bucket}' deleted").format(bucket=args.bucket))


def cmd_object_list(args):
    client = get_client(args.source, args.profile)
    result = client.list_objects(args.bucket, args.prefix, args.delimiter, args.max_keys)

    if args.output == "json":
        import json
        print(json.dumps(result, indent=2))
    else:
        print("{:<50} {:<20} {:>12}".format(_("KEY"), _("LAST MODIFIED"), _("SIZE")))
        print("-" * 90)
        for obj in result.get("objects", []):
            key = obj["Key"][:48] if len(obj["Key"]) > 48 else obj["Key"]
            last_mod = obj.get("LastModified", "")[:19] if obj.get("LastModified") else ""
            size = ReportGenerator.format_size(obj.get("Size", 0))
            print("{:<50} {:<20} {:>12}".format(key, last_mod, size))


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
    print(_("Object '{key}' uploaded, ETag: {etag}").format(key=args.key, etag=result.get('ETag')))


def cmd_object_get(args):
    client = get_client(args.source, args.profile)
    response = client.get_object(args.bucket, args.key)

    with open(args.file, "wb") as f:
        f.write(response["Body"].read())

    print(_("Object '{key}' downloaded to '{file}'").format(key=args.key, file=args.file))


def cmd_object_rm(args):
    client = get_client(args.source, args.profile)
    client.delete_object(args.bucket, args.key, args.version_id)
    print(_("Object '{key}' deleted").format(key=args.key))


def cmd_object_info(args):
    client = get_client(args.source, args.profile)
    info = client.head_object(args.bucket, args.key, args.version_id)

    if args.output == "json":
        import json
        print(json.dumps(info, indent=2))
    else:
        print(_("Object: {key}").format(key=args.key))
        print(_("Bucket: {bucket}").format(bucket=args.bucket))
        print(_("Size: {size}").format(size=ReportGenerator.format_size(info.get('ContentLength', 0))))
        print(_("Last Modified: {time}").format(time=info.get('LastModified', 'N/A')))
        print(_("ETag: {etag}").format(etag=info.get('ETag', 'N/A')))
        print(_("Storage Class: {class_}").format(class_=info.get('StorageClass', 'STANDARD')))

        if info.get("Metadata"):
            print("\n" + _("Metadata:"))
            for k, v in info["Metadata"].items():
                print("  {}: {}".format(k, v))

        if args.include_acl:
            acl = client.get_object_acl(args.bucket, args.key, args.version_id)
            print("\n" + _("ACL:"))
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

    print(_("Object copied, ETag: {etag}").format(etag=result.get('ETag')))


def cmd_metadata_get(args):
    client = get_client(args.source, args.profile)
    metadata_handler = SkyMetadata(client)
    meta = metadata_handler.get(args.bucket, args.key)

    if args.output == "json":
        import json
        print(json.dumps(meta, indent=2))
    else:
        print(_("Metadata for '{key}':").format(key=args.key))
        for k, v in meta.items():
            print("  {}: {}".format(k, v))


def cmd_metadata_set(args):
    client = get_client(args.source, args.profile)
    metadata_handler = SkyMetadata(client)

    metadata = {}
    for m in args.metadata:
        if "=" in m:
            k, v = m.split("=", 1)
            metadata[k] = v

    metadata_handler.set(args.bucket, args.key, metadata, args.operation)
    print(_("Metadata updated for '{key}'").format(key=args.key))


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
    print(_("ACL set for '{key}'").format(key=args.key))


def cmd_acl_cp(args):
    source_client = get_client(args.source, args.profile)
    acl_handler = SkyACL(source_client)
    acl_handler.copy(args.source_bucket, args.source_key, args.target_bucket, args.target_key)
    print(_("ACL copied from '{source_key}' to '{target_key}'").format(
        source_key=args.source_key, target_key=args.target_key
    ))


def cmd_migrate_run(args):
    print("开始迁移...")

    migration = create_sync(
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
        print("\r" + _("Progress: {processed}/{total} ({pct:.1f}%) Failed: {failed}").format(
            processed=progress['processed'],
            total=progress['total'],
            pct=pct,
            failed=progress['failed']
        ), end="", flush=True)

    result = migration.run(progress_callback if not args.quiet else None, args.resume)
    print()

    print(ReportGenerator.generate_migration_report(result, args.output))


def cmd_migrate_list(args):
    history = get_sync_history()
    if not history:
        print(_("No sync history found"))
        return

    for m in history[:args.limit]:
        print(_("{id}: {status} - {source} -> {target}").format(
            id=m.get('sync_id'),
            status=m.get('status'),
            source=m.get('source_bucket'),
            target=m.get('target_bucket')
        ))


def cmd_migrate_status(args):
    sync = get_sync(args.migration_id)
    if not sync:
        print(_("Sync '{id}' not found").format(id=args.migration_id))
        sys.exit(1)

    import json
    print(json.dumps(sync, indent=2))


def cmd_sync_run(args):
    from datetime import datetime

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

        print(_("Dry run - {mode} simulation").format(mode=mode))
        print(_("Source: {source}/{bucket}/{prefix}").format(
            source=args.source, bucket=args.source_bucket, prefix=args.source_prefix or ''
        ))
        print(_("Target: {target}/{bucket}/{prefix}").format(
            target=args.target, bucket=args.target_bucket, prefix=args.target_prefix or ''
        ))
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

        print(_("Objects to upload: {count}").format(count=len(will_upload)))
        print(_("Objects to delete: {count}").format(count=len(will_delete)))
        print(_("Objects to skip: {count}").format(count=len(will_skip)))
        print()

        if will_upload:
            print(_("--- Upload list (first 10) ---"))
            for key in will_upload[:10]:
                print("  " + _("[UPLOAD] {key}").format(key=key))
            if len(will_upload) > 10:
                print("  " + _("... and {count} more").format(count=len(will_upload) - 10))
            print()

        if will_delete:
            print(_("--- Delete list (first 10) ---"))
            for key in will_delete[:10]:
                print("  " + _("[DELETE] {key}").format(key=key))
            if len(will_delete) > 10:
                print("  " + _("... and {count} more").format(count=len(will_delete) - 10))
            print()

        if will_skip:
            print(_("--- Skip list (first 10) ---"))
            for key in will_skip[:10]:
                print("  " + _("[SKIP] {key}").format(key=key))
            if len(will_skip) > 10:
                print("  " + _("... and {count} more").format(count=len(will_skip) - 10))
            print()

        print(_("Dry run completed. No changes were made."))
        return

    print(_("Starting {mode}...").format(mode=mode))

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
        print("\r" + _("Progress: {processed}/{total} ({pct:.1f}%) Uploaded: {uploaded}, Deleted: {deleted}, Skipped: {skipped}, Failed: {failed}").format(
            processed=progress['processed'],
            total=progress['total'],
            pct=pct,
            uploaded=progress['uploaded'],
            deleted=progress['deleted'],
            skipped=progress['skipped'],
            failed=progress['failed']
        ), end="", flush=True)

    result = sync_task.run(progress_callback if not args.quiet else None, args.resume)
    print()

    if mode == "migration":
        print(ReportGenerator.generate_migration_report(result, args.output))
    else:
        print(ReportGenerator.generate_sync_report(result, args.output))


def cmd_sync_list(args):
    history = get_sync_history()
    if not history:
        print(_("No sync history found"))
        return

    for s in history[:args.limit]:
        print(_("{id}: {status} - {source} -> {target}").format(
            id=s.get('sync_id'),
            status=s.get('status'),
            source=s.get('source_bucket'),
            target=s.get('target_bucket')
        ))


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
        print("\r" + _("Validating: {processed}/{total}, failed={failed}").format(
            processed=progress['processed'],
            total=progress['total'],
            failed=progress['failed']
        ), end="", flush=True)

    result = validation.run(progress_callback if not args.quiet else None)
    print()

    print(ReportGenerator.generate_validation_report(result, args.output))


def cmd_validate_report(args):
    report = get_validation_report(args.validation_id)
    if not report:
        print(_("Report '{id}' not found").format(id=args.validation_id))
        sys.exit(1)

    print(ReportGenerator.generate_validation_report(report, args.output))


def cmd_validate_list(args):
    reports = list_validation_reports()
    if not reports:
        print(_("No validation reports found"))
        return

    for r in reports[:args.limit]:
        print(_("{id}: {timestamp} - {status}").format(
            id=r.get('validation_id'),
            timestamp=r.get('timestamp'),
            status=r.get('status')
        ))


def main():
    i18n.init_from_config()

    parser = argparse.ArgumentParser(
        prog="skycli",
        description=_("S3 Compatible Object Storage Manager")
    )
    parser.add_argument("--version", action="version", version="%(prog)s {}".format(__version__))
    subparsers = parser.add_subparsers(dest="command", help=_("Available commands"))

    profile_parser = argparse.ArgumentParser(add_help=False)
    profile_parser.add_argument("--profile", help=_("Config profile name"))

    output_parser = argparse.ArgumentParser(add_help=False)
    output_parser.add_argument("--output", choices=["json", "table"], default="table", help=_("Output format"))

    quiet_parser = argparse.ArgumentParser(add_help=False)
    quiet_parser.add_argument("--quiet", action="store_true", help=_("Quiet mode"))

    config_parser = subparsers.add_parser("config", help=_("Config management"))
    config_subparsers = config_parser.add_subparsers(dest="config_command")

    c_add = config_subparsers.add_parser("add", help=_("Add config"))
    c_add.add_argument("--name", required=True, help=_("Config name"))
    c_add.add_argument("--endpoint", required=True, help=_("S3 endpoint URL"))
    c_add.add_argument("--access-key", required=True, help=_("Access key"))
    c_add.add_argument("--secret-key", required=True, help=_("Secret key"))
    c_add.add_argument("--region", help=_("Region"))
    c_add.add_argument("--use-path-style", action="store_true", help=_("Use path style"))
    c_add.add_argument("--no-verify-ssl", action="store_true", help=_("Disable SSL verification"))
    c_add.add_argument("--signature-version", default="s3v4", help=_("AWS signature version (s3, s3v4, v2, v4, s3v2)"))
    c_add.add_argument("--profile", help=_("Profile name"))
    c_add.set_defaults(func=cmd_config_add)

    c_list = config_subparsers.add_parser("list", help=_("List configs"))
    c_list.add_argument("--profile", help=_("Profile name"))
    c_list.add_argument("--test-all", action="store_true", help=_("Test all connections (slower)"))
    c_list.set_defaults(func=cmd_config_list)

    c_test = config_subparsers.add_parser("test", help=_("Test connection"))
    c_test.add_argument("--name", required=True, help=_("Config name"))
    c_test.add_argument("--profile", help=_("Profile name"))
    c_test.set_defaults(func=cmd_config_test)

    c_rm = config_subparsers.add_parser("rm", help=_("Remove config"))
    c_rm.add_argument("--name", required=True, help=_("Config name"))
    c_rm.add_argument("--profile", help=_("Profile name"))
    c_rm.set_defaults(func=cmd_config_rm)

    bucket_parser = subparsers.add_parser("bucket", help=_("Bucket operations"))
    bucket_subparsers = bucket_parser.add_subparsers(dest="bucket_command")

    b_list = bucket_subparsers.add_parser("list", help=_("List buckets"))
    b_list.add_argument("--source", required=True, help=_("Config name"))
    b_list.add_argument("--profile", help=_("Profile name"))
    b_list.add_argument("--output", choices=["json", "table"], default="table")
    b_list.set_defaults(func=cmd_bucket_list)

    b_info = bucket_subparsers.add_parser("info", help=_("Bucket info"))
    b_info.add_argument("--source", required=True, help=_("Config name"))
    b_info.add_argument("--bucket", required=True, help=_("Bucket name"))
    b_info.add_argument("--profile", help=_("Profile name"))
    b_info.set_defaults(func=cmd_bucket_info)

    b_create = bucket_subparsers.add_parser("create", help=_("Create bucket"))
    b_create.add_argument("--source", required=True, help=_("Config name"))
    b_create.add_argument("--bucket", required=True, help=_("Bucket name"))
    b_create.add_argument("--region", help=_("Region"))
    b_create.add_argument("--profile", help=_("Profile name"))
    b_create.set_defaults(func=cmd_bucket_create)

    b_rm = bucket_subparsers.add_parser("rm", help=_("Delete bucket"))
    b_rm.add_argument("--source", required=True, help=_("Config name"))
    b_rm.add_argument("--bucket", required=True, help=_("Bucket name"))
    b_rm.add_argument("--force", action="store_true", help=_("Force delete"))
    b_rm.add_argument("--profile", help=_("Profile name"))
    b_rm.set_defaults(func=cmd_bucket_rm)

    object_parser = subparsers.add_parser("object", help=_("Object operations"))
    object_subparsers = object_parser.add_subparsers(dest="object_command")

    o_list = object_subparsers.add_parser("list", help=_("List objects"))
    o_list.add_argument("--source", required=True, help=_("Config name"))
    o_list.add_argument("--bucket", required=True, help=_("Bucket name"))
    o_list.add_argument("--prefix", default="", help=_("Prefix filter"))
    o_list.add_argument("--delimiter", help=_("Delimiter"))
    o_list.add_argument("--max-keys", type=int, default=1000, help=_("Max keys"))
    o_list.add_argument("--profile", help=_("Profile name"))
    o_list.add_argument("--output", choices=["json", "table"], default="table")
    o_list.set_defaults(func=cmd_object_list)

    o_put = object_subparsers.add_parser("put", help=_("Upload object"))
    o_put.add_argument("--source", required=True, help=_("Config name"))
    o_put.add_argument("--bucket", required=True, help=_("Bucket name"))
    o_put.add_argument("--key", required=True, help=_("Object key"))
    o_put.add_argument("--file", required=True, help=_("Local file path"))
    o_put.add_argument("--content-type", help=_("Content type"))
    o_put.add_argument("--metadata", nargs="+", help=_("Metadata key=value"))
    o_put.add_argument("--storage-class", help=_("Storage class"))
    o_put.add_argument("--acl", help=_("ACL"))
    o_put.add_argument("--profile", help=_("Profile name"))
    o_put.set_defaults(func=cmd_object_put)

    o_get = object_subparsers.add_parser("get", help=_("Download object"))
    o_get.add_argument("--source", required=True, help=_("Config name"))
    o_get.add_argument("--bucket", required=True, help=_("Bucket name"))
    o_get.add_argument("--key", required=True, help=_("Object key"))
    o_get.add_argument("--file", required=True, help=_("Local file path"))
    o_get.add_argument("--profile", help=_("Profile name"))
    o_get.set_defaults(func=cmd_object_get)

    o_rm = object_subparsers.add_parser("rm", help=_("Delete object"))
    o_rm.add_argument("--source", required=True, help=_("Config name"))
    o_rm.add_argument("--bucket", required=True, help=_("Bucket name"))
    o_rm.add_argument("--key", required=True, help=_("Object key"))
    o_rm.add_argument("--version-id", help=_("Version ID"))
    o_rm.add_argument("--profile", help=_("Profile name"))
    o_rm.set_defaults(func=cmd_object_rm)

    o_info = object_subparsers.add_parser("info", help=_("Object info"))
    o_info.add_argument("--source", required=True, help=_("Config name"))
    o_info.add_argument("--bucket", required=True, help=_("Bucket name"))
    o_info.add_argument("--key", required=True, help=_("Object key"))
    o_info.add_argument("--version-id", help=_("Version ID"))
    o_info.add_argument("--include-metadata", action="store_true", help=_("Include metadata"))
    o_info.add_argument("--include-acl", action="store_true", help=_("Include ACL"))
    o_info.add_argument("--profile", help=_("Profile name"))
    o_info.add_argument("--output", choices=["json", "table"], default="table")
    o_info.set_defaults(func=cmd_object_info)

    o_cp = object_subparsers.add_parser("cp", help=_("Copy object"))
    o_cp.add_argument("--source", required=True, help=_("Source config name"))
    o_cp.add_argument("--source-bucket", required=True, help=_("Source bucket"))
    o_cp.add_argument("--source-key", required=True, help=_("Source key"))
    o_cp.add_argument("--target", required=True, help=_("Target config name"))
    o_cp.add_argument("--target-bucket", required=True, help=_("Target bucket"))
    o_cp.add_argument("--target-key", required=True, help=_("Target key"))
    o_cp.add_argument("--preserve-metadata", action="store_true", help=_("Preserve metadata"))
    o_cp.add_argument("--preserve-acl", action="store_true", help=_("Preserve ACL"))
    o_cp.add_argument("--profile", help=_("Profile name"))
    o_cp.set_defaults(func=cmd_object_cp)

    metadata_parser = subparsers.add_parser("metadata", help=_("Metadata operations"))
    metadata_subparsers = metadata_parser.add_subparsers(dest="metadata_command")

    m_get = metadata_subparsers.add_parser("get", help=_("Get metadata"))
    m_get.add_argument("--source", required=True, help=_("Config name"))
    m_get.add_argument("--bucket", required=True, help=_("Bucket name"))
    m_get.add_argument("--key", required=True, help=_("Object key"))
    m_get.add_argument("--profile", help=_("Profile name"))
    m_get.add_argument("--output", choices=["json", "table"], default="table")
    m_get.set_defaults(func=cmd_metadata_get)

    m_set = metadata_subparsers.add_parser("set", help=_("Set metadata"))
    m_set.add_argument("--source", required=True, help=_("Config name"))
    m_set.add_argument("--bucket", required=True, help=_("Bucket name"))
    m_set.add_argument("--key", required=True, help=_("Object key"))
    m_set.add_argument("--metadata", nargs="+", required=True, help=_("Metadata key=value"))
    m_set.add_argument("--operation", choices=["COPY", "REPLACE"], default="REPLACE")
    m_set.add_argument("--profile", help=_("Profile name"))
    m_set.set_defaults(func=cmd_metadata_set)

    acl_parser = subparsers.add_parser("acl", help=_("ACL operations"))
    acl_subparsers = acl_parser.add_subparsers(dest="acl_command")

    a_get = acl_subparsers.add_parser("get", help=_("Get ACL"))
    a_get.add_argument("--source", required=True, help=_("Config name"))
    a_get.add_argument("--bucket", required=True, help=_("Bucket name"))
    a_get.add_argument("--key", help=_("Object key"))
    a_get.add_argument("--profile", help=_("Profile name"))
    a_get.add_argument("--output", choices=["json", "table"], default="table")
    a_get.set_defaults(func=cmd_acl_get)

    a_set = acl_subparsers.add_parser("set", help=_("Set ACL"))
    a_set.add_argument("--source", required=True, help=_("Config name"))
    a_set.add_argument("--bucket", required=True, help=_("Bucket name"))
    a_set.add_argument("--key", help=_("Object key"))
    a_set.add_argument("--acl", help=_("Canned ACL"))
    a_set.add_argument("--grant-read", action="store_true", help=_("Grant read"))
    a_set.add_argument("--grant-full-control", action="store_true", help=_("Grant full control"))
    a_set.add_argument("--profile", help=_("Profile name"))
    a_set.set_defaults(func=cmd_acl_set)

    a_cp = acl_subparsers.add_parser("cp", help=_("Copy ACL"))
    a_cp.add_argument("--source", required=True, help=_("Source config name"))
    a_cp.add_argument("--source-bucket", required=True, help=_("Source bucket"))
    a_cp.add_argument("--source-key", required=True, help=_("Source key"))
    a_cp.add_argument("--target", required=True, help=_("Target config name"))
    a_cp.add_argument("--target-bucket", required=True, help=_("Target bucket"))
    a_cp.add_argument("--target-key", required=True, help=_("Target key"))
    a_cp.add_argument("--profile", help=_("Profile name"))
    a_cp.set_defaults(func=cmd_acl_cp)

    sync_parser = subparsers.add_parser("sync", help=_("Sync/Migration operations"))
    sync_subparsers = sync_parser.add_subparsers(dest="sync_command")

    s_run = sync_subparsers.add_parser("run", help=_("Run sync/migration"))
    s_run.add_argument("--source", required=True, help=_("Source config name"))
    s_run.add_argument("--source-bucket", required=True, help=_("Source bucket"))
    s_run.add_argument("--source-prefix", help=_("Source prefix"))
    s_run.add_argument("--target", required=True, help=_("Target config name"))
    s_run.add_argument("--target-bucket", required=True, help=_("Target bucket"))
    s_run.add_argument("--target-prefix", help=_("Target prefix"))
    s_run.add_argument("--since", help=_("Sync since (ISO format)"))
    s_run.add_argument("--since-last-sync", action="store_true", help=_("Sync since last sync"))
    s_run.add_argument("--delete", action="store_true", help=_("Delete objects not in source (sync mode)"))
    s_run.add_argument("--threads", type=int, default=10, help=_("Threads"))
    s_run.add_argument("--part-size", type=int, default=8, help=_("Part size (MB)"))
    s_run.add_argument("--storage-class", help=_("Storage class"))
    s_run.add_argument("--preserve-metadata", action="store_true", help=_("Preserve metadata"))
    s_run.add_argument("--preserve-acl", action="store_true", help=_("Preserve ACL"))
    s_run.add_argument("--exclude", nargs="+", help=_("Exclude patterns"))
    s_run.add_argument("--include", nargs="+", help=_("Include patterns"))
    s_run.add_argument("--dry-run", action="store_true", help=_("Dry run"))
    s_run.add_argument("--resume", action="store_true", help=_("Resume migration"))
    s_run.add_argument("--profile", help=_("Profile name"))
    s_run.add_argument("--output", choices=["json", "table"], default="table")
    s_run.add_argument("--quiet", action="store_true", help=_("Quiet mode"))
    s_run.set_defaults(func=cmd_sync_run)

    s_list = sync_subparsers.add_parser("list", help=_("List sync/migration history"))
    s_list.add_argument("--limit", type=int, default=10, help=_("Limit"))
    s_list.set_defaults(func=cmd_sync_list)

    s_status = sync_subparsers.add_parser("status", help=_("Sync/migration status"))
    s_status.add_argument("--migration-id", required=True, help=_("Migration ID"))
    s_status.set_defaults(func=cmd_migrate_status)

    validate_parser = subparsers.add_parser("validate", help=_("Validation operations"))
    validate_subparsers = validate_parser.add_subparsers(dest="validate_command")

    v_run = validate_subparsers.add_parser("run", help=_("Run validation"))
    v_run.add_argument("--source", required=True, help=_("Source config name"))
    v_run.add_argument("--source-bucket", required=True, help=_("Source bucket"))
    v_run.add_argument("--target", required=True, help=_("Target config name"))
    v_run.add_argument("--target-bucket", required=True, help=_("Target bucket"))
    v_run.add_argument("--prefix", help=_("Prefix filter"))
    v_run.add_argument("--check", choices=["content", "metadata", "acl", "all"], default="all", help=_("What to check"))
    v_run.add_argument("--fields", help=_("Metadata fields to check (comma-separated)"))
    v_run.add_argument("--threads", type=int, default=10, help=_("Threads"))
    v_run.add_argument("--profile", help=_("Profile name"))
    v_run.add_argument("--output", choices=["json", "table"], default="table")
    v_run.add_argument("--quiet", action="store_true", help=_("Quiet mode"))
    v_run.set_defaults(func=cmd_validate_run)

    v_report = validate_subparsers.add_parser("report", help=_("Show validation report"))
    v_report.add_argument("--validation-id", required=True, help=_("Validation ID"))
    v_report.add_argument("--output", choices=["json", "table"], default="table")
    v_report.set_defaults(func=cmd_validate_report)

    v_list = validate_subparsers.add_parser("list", help=_("List validation reports"))
    v_list.add_argument("--limit", type=int, default=10, help=_("Limit"))
    v_list.set_defaults(func=cmd_validate_list)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if hasattr(args, "func"):
        try:
            args.func(args)
        except Exception as e:
            print(_("Error: {error}").format(error=e))
            if hasattr(args, "debug") and args.debug:
                import traceback
                traceback.print_exc()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
