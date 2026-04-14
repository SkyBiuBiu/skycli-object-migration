import argparse
import sys
import os
from typing import Optional, List, Dict


class SmartFormatter(argparse.RawDescriptionHelpFormatter):
    def __init__(self, *args, **kwargs):
        import shutil
        width = shutil.get_terminal_size().columns
        kwargs.setdefault('width', min(width, 120))
        super().__init__(*args, **kwargs)


from .skyconfig import SkyConfig
from .skyclient import SkyClient
from ._version import get_version
from .skyreport import ReportGenerator
from .constants import CLI_STATUS_MESSAGES
from .i18n import _
from .skysync import create_sync, SyncTask
from .skyvalidate import create_validation, ValidationTask
from .skymetadata import SkyMetadata
from .skyacl import SkyACL

config = SkyConfig()


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

    name_width = max(len(_("NAME")), max(len(p['name']) for p in profiles)) + 2
    endpoint_width = max(len(_("ENDPOINT")), max(len(p['endpoint']) for p in profiles)) + 2
    region_width = max(len(_("REGION")), max(len(p.get('region', '-')) for p in profiles)) + 2

    if not args.test_all:
        header = f"{_('NAME'):<{name_width}} {_('ENDPOINT'):<{endpoint_width}} {_('REGION'):<{region_width}}"
        print(header)
        print("-" * (name_width + endpoint_width + region_width + 2))
        for p in sorted(profiles, key=lambda x: x["name"]):
            print(f"{p['name']:<{name_width}} {p['endpoint']:<{endpoint_width}} {p.get('region', '-'):<{region_width}}")
        print("\n" + _("Tip: Use --test-all to test connection status"))
        return

    status_width = 12
    header = f"{_('NAME'):<{name_width}} {_('ENDPOINT'):<{endpoint_width}} {_('REGION'):<{region_width}} {_('STATUS')}"
    print(header)
    print("-" * (name_width + endpoint_width + region_width + status_width + 3))

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

    for name, endpoint, region, success, error in sorted(results):
        if success:
            status = CLI_STATUS_MESSAGES["success"]
        elif error and "Connection" in error:
            status = CLI_STATUS_MESSAGES["connection_failed"]
        elif error:
            status = CLI_STATUS_MESSAGES["error"]
        else:
            status = CLI_STATUS_MESSAGES["failed"]
        print(f"{name:<{name_width}} {endpoint:<{endpoint_width}} {region:<{region_width}} {status}")


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


def cmd_config_show(args):
    profile = config.get_profile(args.name, args.profile)
    if not profile:
        print(_("Config '{name}' not found").format(name=args.name))
        sys.exit(1)

    print(_("Name:        {name}").format(name=args.name))
    print(_("Endpoint:    {endpoint}").format(endpoint=profile.get('endpoint', 'N/A')))
    print(_("Region:      {region}").format(region=profile.get('region', 'N/A')))
    print(_("Access Key:  {access_key}").format(access_key=profile.get('access_key', 'N/A')))
    print(_("Secret Key:  {secret_key}").format(secret_key='*' * len(profile.get('secret_key', '')) if profile.get('secret_key') else 'N/A'))
    print(_("Path Style:  {use_path_style}").format(use_path_style=profile.get('use_path_style', False)))
    print(_("SSL Verify:  {verify_ssl}").format(verify_ssl=profile.get('verify_ssl', True)))
    print(_("Signature:   {signature_version}").format(signature_version=profile.get('signature_version', 's3v4')))


def cmd_bucket_list(args):
    client = get_client(args.source, args.profile)
    buckets = client.list_buckets()

    if not buckets:
        print(_("No buckets found"))
        return

    if args.output == "table":
        print("{:<30} {:<20}".format(_("BUCKET NAME"), _("CREATION DATE")))
        print("-" * 52)
        for bucket in buckets:
            creation_date = bucket.get("CreationDate", "N/A")
            if hasattr(creation_date, 'strftime'):
                creation_date = creation_date.strftime("%Y-%m-%d %H:%M:%S")
            print("{:<30} {:<20}".format(bucket["Name"], str(creation_date)))
    else:
        import json
        print(json.dumps(buckets, indent=2, default=str))


def cmd_bucket_create(args):
    client = get_client(args.target, args.profile)
    try:
        client.create_bucket(args.bucket, region=args.region)
        print(_("Bucket '{bucket}' created successfully").format(bucket=args.bucket))
    except Exception as e:
        print(_("Failed to create bucket: {error}").format(error=str(e)))
        sys.exit(1)


def cmd_object_list(args):
    client = get_client(args.source, args.profile)

    kwargs = {"bucket": args.bucket, "prefix": args.prefix or ""}
    if args.delimiter:
        kwargs["delimiter"] = args.delimiter
    if args.continuation_token:
        kwargs["continuation_token"] = args.continuation_token

    result = client.list_objects(**kwargs)

    objects = result.get("objects", [])
    if not objects:
        print(_("No objects found"))
        return

    if args.output == "table":
        print("{:<40} {:>12} {:<20}".format(_("KEY"), _("SIZE"), _("LAST MODIFIED")))
        print("-" * 74)
        for obj in objects:
            last_modified = obj.get("LastModified", "N/A")
            if hasattr(last_modified, 'strftime'):
                last_modified = last_modified.strftime("%Y-%m-%d %H:%M:%S")
            size = obj.get("Size", 0)
            size_str = f"{size:,}" if isinstance(size, int) else str(size)
            print("{:<40} {:>12} {:<20}".format(obj.get("Key", ""), size_str, last_modified))
    else:
        import json
        print(json.dumps(result, indent=2, default=str))

    if result.get("is_truncated"):
        print("\n" + _("Note: Results are truncated. Use --continuation-token for next page."))


def cmd_object_info(args):
    client = get_client(args.source, args.profile)

    try:
        info = client.head_object(args.bucket, args.key)
        if args.output == "table":
            print(_("Object: {bucket}/{key}").format(bucket=args.bucket, key=args.key))
            print("-" * 50)
            print(_("Content-Type:  {content_type}").format(content_type=info.get("ContentType", "N/A")))
            print(_("Content-Length: {size}").format(size=info.get("ContentLength", "N/A")))
            print(_("Last-Modified: {last_modified}").format(last_modified=info.get("LastModified", "N/A")))
            print(_("ETag:          {etag}").format(etag=info.get("ETag", "N/A")))
            print(_("StorageClass:  {storage_class}").format(storage_class=info.get("StorageClass", "STANDARD")))
            metadata = info.get("Metadata", {})
            if metadata:
                print(_("Metadata:"))
                for key, value in metadata.items():
                    print(_("  {key}: {value}").format(key=key, value=value))
        else:
            import json
            print(json.dumps(info, indent=2, default=str))
    except Exception as e:
        print(_("Failed to get object info: {error}").format(error=str(e)))
        sys.exit(2)


def cmd_object_cp(args):
    client = get_client(args.source, args.profile)
    target_client = get_client(args.target, args.profile)

    try:
        target_key = args.target_key or args.source_key

        result = target_client.copy_object(
            source_bucket=args.source_bucket,
            source_key=args.source_key,
            target_bucket=args.target_bucket,
            target_key=target_key,
            storage_class="STANDARD"
        )

        if args.preserve_metadata:
            source_info = client.head_object(args.source_bucket, args.source_key)
            metadata = source_info.get("Metadata", {})
            if metadata:
                target_client.put_object(
                    bucket=args.target_bucket,
                    key=target_key,
                    data=b"",
                    metadata=metadata
                )

        print(_("[OK] Object copied successfully"))
        print(_("  ETag: {etag}").format(etag=result.get("ETag", "N/A")))
        print(_("  Key: {bucket}/{key}").format(bucket=args.target_bucket, key=target_key))
    except Exception as e:
        print(_("[FAIL] Copy failed: {error}").format(error=str(e)))
        sys.exit(1)


def cmd_sync_run(args):
    from .skysync import create_sync, SyncTask
    from .skyreport import ReportGenerator

    since = None
    if args.since:
        from datetime import datetime
        since = datetime.fromisoformat(args.since.replace("Z", "+00:00"))

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
        profile=args.profile,
        dry_run=args.dry_run
    )

    def progress_callback(progress_info):
        if not args.quiet:
            current = progress_info.get("processed", 0)
            total = progress_info.get("total", 0)
            percentage = (current / total * 100) if total > 0 else 0
            sys.stdout.write("\rProgress: {}/{} ({:.1f}%)".format(
                current, total, percentage))
            sys.stdout.flush()

    result = sync_task.run(progress_callback if not args.quiet else None, args.resume)

    if not args.quiet:
        print()

    report = ReportGenerator.generate_sync_report(sync_task.get_summary(), output_format=args.output)
    print(report)

    if sync_task.failed > 0:
        sys.exit(1)


def cmd_sync_history(args):
    from .skysync import get_sync_history

    history = get_sync_history(limit=args.limit)

    if not history:
        print(_("No sync history found"))
        return

    print("{:<20} {:<15} {:<10} {:>10} {:>10} {:>10}".format(
        _("TIME"), _("STATUS"), _("SOURCE"), _("TOTAL"), _("SUCCESS"), _("FAILED")
    ))
    print("-" * 80)

    for item in history:
        time_str = item.get("start_time", "N/A")
        status = item.get("status", "N/A")
        source = item.get("source_bucket", "N/A")
        total = item.get("total_objects", 0)
        success = item.get("uploaded", 0) + item.get("skipped", 0)
        failed = item.get("failed", 0)

        if hasattr(time_str, 'strftime'):
            time_str = time_str.strftime("%Y-%m-%d %H:%M")
        elif isinstance(time_str, str) and "T" in time_str:
            try:
                time_str = datetime.fromisoformat(time_str.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
            except:
                pass
        
        print("{:<20} {:<15} {:<10} {:>10} {:>10} {:>10}".format(
            str(time_str)[:20], status, source, total, success, failed
        ))


def cmd_validate_run(args):
    from .skyvalidate import create_validation, ValidationTask
    from .skyreport import ReportGenerator

    validation = create_validation(
        source_config_name=args.source,
        source_bucket=args.source_bucket,
        target_config_name=args.target,
        target_bucket=args.target_bucket,
        prefix=args.source_prefix or "",
        check_content=not args.skip_content,
        check_metadata=not args.no_check_metadata,
        check_acl=not args.no_check_acl,
        profile=args.profile
    )

    def progress_callback(progress_info):
        if not args.quiet:
            current = progress_info.get("processed", 0)
            total = progress_info.get("total", 0)
            percentage = (current / total * 100) if total > 0 else 0
            sys.stdout.write("\rValidating: {}/{} ({:.1f}%)".format(
                current, total, percentage))
            sys.stdout.flush()

    result = validation.run(progress_callback if not args.quiet else None)

    if not args.quiet:
        print()

    report = ReportGenerator.generate_validation_report(validation.get_report(), output_format=args.output)
    print(report)

    if validation.failed > 0:
        sys.exit(1)


def cmd_metadata_get(args):
    client = get_client(args.source, args.profile)

    try:
        info = client.head_object(args.bucket, args.key)
        print(_("Metadata for: {bucket}/{key}").format(bucket=args.bucket, key=args.key))
        print(_("-" * 50))
        print(_("Content-Type:  {content_type}").format(content_type=info.get("ContentType", "N/A")))
        print(_("Content-Length: {size}").format(size=info.get("ContentLength", "N/A")))
        print(_("Last-Modified: {last_modified}").format(last_modified=info.get("LastModified", "N/A")))
        print(_("ETag:          {etag}").format(etag=info.get("ETag", "N/A")))

        metadata = info.get("Metadata", {})
        if metadata:
            print(_("Custom Metadata:"))
            for key, value in metadata.items():
                print(_("  {key}: {value}").format(key=key, value=value))
        else:
            print(_("Custom Metadata: (none)"))
    except Exception as e:
        print(_("Failed to get metadata: {error}").format(error=str(e)))
        sys.exit(1)


def cmd_acl_get(args):
    client = get_client(args.source, args.profile)

    try:
        acl = client.get_object_acl(args.bucket, args.key)
        print(_("ACL for: {bucket}/{key}").format(bucket=args.bucket, key=args.key))
        print(_("-" * 50))

        owner = acl.get("Owner", {})
        if owner:
            print(_("Owner: {owner}").format(owner=owner.get("DisplayName", owner.get("ID", "N/A"))))

        grants = acl.get("Grants", [])
        if grants:
            print(_("Grants:"))
            for grant in grants:
                grantee = grant.get("Grantee", {})
                permission = grant.get("Permission", "N/A")
                uri = grantee.get("URI", "")

                if uri:
                    if uri.endswith("AllUsers"):
                        grantee_info = "AllUsers (public)"
                    elif uri.endswith("AuthenticatedUsers"):
                        grantee_info = "AuthenticatedUsers"
                    else:
                        grantee_info = uri
                else:
                    grantee_info = grantee.get("DisplayName", grantee.get("ID", "N/A"))

                print(_("  {permission}: {grantee}").format(permission=permission, grantee=grantee_info))
        else:
            print(_("Grants: (none)"))
    except Exception as e:
        print(_("Failed to get ACL: {error}").format(error=str(e)))
        sys.exit(1)


def build_parser():
    parser = argparse.ArgumentParser(
        description=_("SkyCLI - S3 object storage management tool"),
        formatter_class=SmartFormatter
    )

    parser.add_argument("--version", action="version", version="skycli {version}".format(version=get_version()))

    subparsers = parser.add_subparsers(dest="command", title=_("Commands"))

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

    c_show = config_subparsers.add_parser("show", help=_("Show config details"))
    c_show.add_argument("--name", required=True, help=_("Config name"))
    c_show.add_argument("--profile", help=_("Profile name"))
    c_show.set_defaults(func=cmd_config_show)

    o_ls = subparsers.add_parser("ls", help=_("List buckets"))
    o_ls.add_argument("source", help=_("Config name"))
    o_ls.add_argument("--output", choices=["table", "json"], default="table", help=_("Output format"))
    o_ls.add_argument("--profile", help=_("Profile name"))
    o_ls.set_defaults(func=cmd_bucket_list)

    o_ls = subparsers.add_parser("bucket", help=_("Bucket operations"))
    bucket_subparsers = o_ls.add_subparsers(dest="bucket_command")

    bucket_ls = bucket_subparsers.add_parser("list", help=_("List buckets"))
    bucket_ls.add_argument("source", help=_("Config name"))
    bucket_ls.add_argument("--output", choices=["table", "json"], default="table", help=_("Output format"))
    bucket_ls.add_argument("--profile", help=_("Profile name"))
    bucket_ls.set_defaults(func=cmd_bucket_list)

    bucket_mk = bucket_subparsers.add_parser("create", help=_("Create bucket"))
    bucket_mk.add_argument("target", help=_("Target config name"))
    bucket_mk.add_argument("bucket", help=_("Bucket name"))
    bucket_mk.add_argument("--region", help=_("Region"))
    bucket_mk.add_argument("--profile", help=_("Profile name"))
    bucket_mk.set_defaults(func=cmd_bucket_create)

    o_ls = subparsers.add_parser("object", help=_("Object operations"))
    object_subparsers = o_ls.add_subparsers(dest="object_command")

    obj_ls = object_subparsers.add_parser("list", help=_("List objects"))
    obj_ls.add_argument("--source", required=True, help=_("Config name"))
    obj_ls.add_argument("--bucket", required=True, help=_("Bucket name"))
    obj_ls.add_argument("--prefix", help=_("Prefix filter"))
    obj_ls.add_argument("--delimiter", help=_("Delimiter"))
    obj_ls.add_argument("--continuation-token", help=_("Continuation token for pagination"))
    obj_ls.add_argument("--output", choices=["table", "json"], default="table", help=_("Output format"))
    obj_ls.add_argument("--profile", help=_("Profile name"))
    obj_ls.set_defaults(func=cmd_object_list)

    obj_info = object_subparsers.add_parser("info", help=_("Get object info"))
    obj_info.add_argument("--source", required=True, help=_("Config name"))
    obj_info.add_argument("--bucket", required=True, help=_("Bucket name"))
    obj_info.add_argument("--key", required=True, help=_("Object key"))
    obj_info.add_argument("--output", choices=["table", "json"], default="table", help=_("Output format"))
    obj_info.add_argument("--profile", help=_("Profile name"))
    obj_info.set_defaults(func=cmd_object_info)

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
    m_get.set_defaults(func=cmd_metadata_get)

    acl_parser = subparsers.add_parser("acl", help=_("ACL operations"))
    acl_subparsers = acl_parser.add_subparsers(dest="acl_command")

    acl_get = acl_subparsers.add_parser("get", help=_("Get ACL"))
    acl_get.add_argument("--source", required=True, help=_("Config name"))
    acl_get.add_argument("--bucket", required=True, help=_("Bucket name"))
    acl_get.add_argument("--key", required=True, help=_("Object key"))
    acl_get.add_argument("--profile", help=_("Profile name"))
    acl_get.set_defaults(func=cmd_acl_get)

    sync_parser = subparsers.add_parser("sync", help=_("Sync/Migration operations"))
    sync_subparsers = sync_parser.add_subparsers(dest="sync_command")

    s_run = sync_subparsers.add_parser("run", help=_("Run sync"))
    s_run.add_argument("--source", required=True, help=_("Source config name"))
    s_run.add_argument("--source-bucket", required=True, help=_("Source bucket"))
    s_run.add_argument("--source-prefix", help=_("Source prefix"))
    s_run.add_argument("--target", required=True, help=_("Target config name"))
    s_run.add_argument("--target-bucket", required=True, help=_("Target bucket"))
    s_run.add_argument("--target-prefix", help=_("Target prefix"))
    s_run.add_argument("--since", help=_("Sync since datetime (ISO format)"))
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

    s_history = sync_subparsers.add_parser("history", help=_("Sync history"))
    s_history.add_argument("--limit", type=int, default=20, help=_("Number of records"))
    s_history.set_defaults(func=cmd_sync_history)

    validate_parser = subparsers.add_parser("validate", help=_("Validation operations"))
    validate_subparsers = validate_parser.add_subparsers(dest="validate_command")

    v_run = validate_subparsers.add_parser("run", help=_("Run validation"))
    v_run.add_argument("--source", required=True, help=_("Source config name"))
    v_run.add_argument("--source-bucket", required=True, help=_("Source bucket"))
    v_run.add_argument("--source-prefix", help=_("Source prefix"))
    v_run.add_argument("--target", required=True, help=_("Target config name"))
    v_run.add_argument("--target-bucket", required=True, help=_("Target bucket"))
    v_run.add_argument("--target-prefix", help=_("Target prefix"))
    v_run.add_argument("--skip-content", action="store_true", help=_("Skip content comparison"))
    v_run.add_argument("--no-check-metadata", action="store_true", help=_("Skip metadata comparison"))
    v_run.add_argument("--no-check-acl", action="store_true", help=_("Skip ACL comparison"))
    v_run.add_argument("--profile", help=_("Profile name"))
    v_run.add_argument("--output", choices=["json", "table"], default="table")
    v_run.add_argument("--quiet", action="store_true", help=_("Quiet mode"))
    v_run.set_defaults(func=cmd_validate_run)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except KeyboardInterrupt:
        print(_("\nOperation cancelled by user"))
        sys.exit(130)
    except Exception as e:
        print(_("Error: {error}").format(error=str(e)))
        if os.getenv("DEBUG"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
