import boto3
import botocore
from botocore.config import Config
from typing import Dict, List, Optional, Any, Iterator
from datetime import datetime


class SkyClient:
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        use_path_style: bool = False,
        verify_ssl: bool = True
    ):
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.use_path_style = use_path_style
        self.verify_ssl = verify_ssl

        self._client = self._create_client()
        self._resource = self._create_resource()

    def _create_client(self):
        config = Config(
            region_name=self.region,
            signature_version="s3v4",
            s3={"addressing_style": "path" if self.use_path_style else "auto"},
            retries={"max_attempts": 3, "mode": "standard"}
        )

        return boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=config,
            verify=self.verify_ssl
        )

    def _create_resource(self):
        config = Config(
            region_name=self.region,
            signature_version="s3v4",
            s3={"addressing_style": "path" if self.use_path_style else "auto"}
        )

        return boto3.resource(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=config,
            verify=self.verify_ssl
        )

    def test_connection(self) -> Dict:
        try:
            response = self._client.list_buckets()
            buckets = [b["Name"] for b in response.get("Buckets", [])]
            return {
                "success": True,
                "bucket_count": len(buckets),
                "buckets": buckets[:10]
            }
        except botocore.exceptions.ClientError as e:
            return {
                "success": False,
                "error": str(e)
            }

    def list_buckets(self) -> List[Dict]:
        response = self._client.list_buckets()
        return [
            {
                "Name": b["Name"],
                "CreationDate": b["CreationDate"].isoformat() if b.get("CreationDate") else None
            }
            for b in response.get("Buckets", [])
        ]

    def list_objects(
        self,
        bucket: str,
        prefix: str = "",
        delimiter: Optional[str] = None,
        max_keys: int = 1000,
        continuation_token: Optional[str] = None
    ) -> Dict:
        kwargs = {
            "Bucket": bucket,
            "Prefix": prefix,
            "MaxKeys": max_keys
        }

        if delimiter:
            kwargs["Delimiter"] = delimiter
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token

        response = self._client.list_objects_v2(**kwargs)

        objects = []
        for obj in response.get("Contents", []):
            objects.append({
                "Key": obj["Key"],
                "LastModified": obj["LastModified"].isoformat() if obj.get("LastModified") else None,
                "Size": obj.get("Size", 0),
                "StorageClass": obj.get("StorageClass", "STANDARD"),
                "ETag": obj.get("ETag", "").strip('"'),
                "VersionId": obj.get("VersionId")
            })

        return {
            "objects": objects,
            "prefix": prefix,
            "is_truncated": response.get("IsTruncated", False),
            "next_continuation_token": response.get("NextContinuationToken"),
            "key_count": len(objects)
        }

    def list_objects_all(self, bucket: str, prefix: str = "") -> Iterator[Dict]:
        continuation_token = None

        while True:
            result = self.list_objects(
                bucket=bucket,
                prefix=prefix,
                continuation_token=continuation_token
            )

            for obj in result["objects"]:
                yield obj

            if not result["is_truncated"]:
                break

            continuation_token = result["next_continuation_token"]

    def head_object(self, bucket: str, key: str, version_id: Optional[str] = None) -> Dict:
        kwargs = {"Bucket": bucket, "Key": key}
        if version_id:
            kwargs["VersionId"] = version_id

        response = self._client.head_object(**kwargs)

        return {
            "ContentLength": response.get("ContentLength"),
            "ContentType": response.get("ContentType"),
            "ContentMD5": response.get("ContentMD5"),
            "LastModified": response["LastModified"].isoformat() if response.get("LastModified") else None,
            "ETag": response.get("ETag", "").strip('"'),
            "StorageClass": response.get("StorageClass", "STANDARD"),
            "Metadata": response.get("Metadata", {}),
            "VersionId": response.get("VersionId"),
            "CacheControl": response.get("CacheControl"),
            "Expires": response.get("Expires").isoformat() if response.get("Expires") else None
        }

    def get_object(self, bucket: str, key: str, version_id: Optional[str] = None) -> Any:
        kwargs = {"Bucket": bucket, "Key": key}
        if version_id:
            kwargs["VersionId"] = version_id

        return self._client.get_object(**kwargs)

    def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes,
        metadata: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None,
        cache_control: Optional[str] = None,
        storage_class: str = "STANDARD",
        acl: Optional[str] = None
    ) -> Dict:
        kwargs = {
            "Bucket": bucket,
            "Key": key,
            "Body": body,
            "StorageClass": storage_class
        }

        if metadata:
            kwargs["Metadata"] = metadata
        if content_type:
            kwargs["ContentType"] = content_type
        if cache_control:
            kwargs["CacheControl"] = cache_control
        if acl:
            kwargs["ACL"] = acl

        response = self._client.put_object(**kwargs)

        return {
            "ETag": response.get("ETag", "").strip('"'),
            "VersionId": response.get("VersionId")
        }

    def delete_object(self, bucket: str, key: str, version_id: Optional[str] = None) -> bool:
        kwargs = {"Bucket": bucket, "Key": key}
        if version_id:
            kwargs["VersionId"] = version_id

        self._client.delete_object(**kwargs)
        return True

    def copy_object(
        self,
        source_bucket: str,
        source_key: str,
        target_bucket: str,
        target_key: str,
        metadata: Optional[Dict[str, str]] = None,
        metadata_directive: str = "COPY",
        content_type: Optional[str] = None,
        cache_control: Optional[str] = None,
        storage_class: str = "STANDARD",
        acl: Optional[str] = None,
        source_version_id: Optional[str] = None
    ) -> Dict:
        copy_source = f"{source_bucket}/{source_key}"
        if source_version_id:
            copy_source += f"?versionId={source_version_id}"

        kwargs = {
            "Bucket": target_bucket,
            "Key": target_key,
            "CopySource": copy_source,
            "StorageClass": storage_class
        }

        if metadata_directive == "COPY":
            kwargs["MetadataDirective"] = "COPY"
        elif metadata_directive == "REPLACE" and metadata:
            kwargs["MetadataDirective"] = "REPLACE"
            kwargs["Metadata"] = metadata

        if content_type:
            kwargs["ContentType"] = content_type
        if cache_control:
            kwargs["CacheControl"] = cache_control
        if acl:
            kwargs["ACL"] = acl

        response = self._client.copy_object(**kwargs)

        return {
            "ETag": response.get("ETag", "").strip('"'),
            "VersionId": response.get("VersionId")
        }

    def upload_file(self, bucket: str, key: str, file_path: str, metadata: Optional[Dict[str, str]] = None,
                    content_type: Optional[str] = None, storage_class: str = "STANDARD", acl: Optional[str] = None,
                    extra_args: Optional[Dict] = None) -> Dict:
        kwargs = {"Bucket": bucket, "Key": key, "Filename": file_path}

        if metadata:
            kwargs["Metadata"] = metadata
        if content_type:
            kwargs["ExtraArgs"] = extra_args or {}
            kwargs["ExtraArgs"]["ContentType"] = content_type
        if storage_class:
            kwargs["ExtraArgs"] = kwargs.get("ExtraArgs") or {}
            kwargs["ExtraArgs"]["StorageClass"] = storage_class
        if acl:
            kwargs["ExtraArgs"] = kwargs.get("ExtraArgs") or {}
            kwargs["ExtraArgs"]["ACL"] = acl

        self._client.upload_file(**kwargs)
        return {"success": True}

    def download_file(self, bucket: str, key: str, file_path: str, version_id: Optional[str] = None):
        kwargs = {"Bucket": bucket, "Key": key, "Filename": file_path}
        if version_id:
            kwargs["VersionId"] = version_id

        self._client.download_file(**kwargs)

    def get_object_acl(self, bucket: str, key: str, version_id: Optional[str] = None) -> Dict:
        kwargs = {"Bucket": bucket, "Key": key}
        if version_id:
            kwargs["VersionId"] = version_id

        response = self._client.get_object_acl(**kwargs)

        return {
            "Owner": {
                "ID": response["Owner"]["ID"],
                "DisplayName": response["Owner"].get("DisplayName")
            },
            "Grants": [
                {
                    "Grantee": {
                        "Type": g["Grantee"].get("Type"),
                        "ID": g["Grantee"].get("ID"),
                        "DisplayName": g["Grantee"].get("DisplayName"),
                        "URI": g["Grantee"].get("URI")
                    },
                    "Permission": g["Permission"]
                }
                for g in response.get("Grants", [])
            ]
        }

    def put_object_acl(self, bucket: str, key: str, acl: Optional[str] = None,
                        grant_read: Optional[str] = None, grant_full_control: Optional[str] = None,
                        grant_write: Optional[str] = None, grant_read_acp: Optional[str] = None,
                        grant_write_acp: Optional[str] = None, version_id: Optional[str] = None):
        kwargs = {"Bucket": bucket, "Key": key}

        if version_id:
            kwargs["VersionId"] = version_id

        if acl:
            kwargs["ACL"] = acl

        if grant_read or grant_full_control or grant_write or grant_read_acp or grant_write_acp:
            kwargs["AccessControlPolicy"] = {"Grants": [], "Owner": {}}
            grants = []
            if grant_read:
                grants.append({"Grantee": {"Type": "uri", "URI": "http://acs.amazonaws.com/groups/global/AllUsers"},
                              "Permission": "READ"})
            if grant_full_control:
                grants.append({"Grantee": {"Type": "uri", "URI": "http://acs.amazonaws.com/groups/global/AllUsers"},
                              "Permission": "FULL_CONTROL"})
            kwargs["AccessControlPolicy"]["Grants"] = grants

        self._client.put_object_acl(**kwargs)

    def create_bucket(self, bucket: str, region: Optional[str] = None):
        kwargs = {"Bucket": bucket}
        if region and region != "us-east-1":
            kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
        self._client.create_bucket(**kwargs)

    def delete_bucket(self, bucket: str):
        self._client.delete_bucket(Bucket=bucket)

    def bucket_exists(self, bucket: str) -> bool:
        try:
            self._client.head_bucket(Bucket=bucket)
            return True
        except:
            return False

    def get_bucket_location(self, bucket: str) -> str:
        response = self._client.get_bucket_location(Bucket=bucket)
        return response.get("LocationConstraint") or "us-east-1"

    def get_bucket_policy(self, bucket: str) -> Optional[Dict]:
        try:
            response = self._client.get_bucket_policy(Bucket=bucket)
            import json
            return json.loads(response["Policy"])
        except:
            return None

    def put_bucket_policy(self, bucket: str, policy: Dict):
        import json
        policy_str = json.dumps(policy)
        self._client.put_bucket_policy(Bucket=bucket, Policy=policy_str)

    def delete_bucket_policy(self, bucket: str):
        self._client.delete_bucket_policy(Bucket=bucket)

    def get_bucket_acl(self, bucket: str) -> Dict:
        response = self._client.get_bucket_acl(Bucket=bucket)
        return {
            "Owner": {
                "ID": response["Owner"]["ID"],
                "DisplayName": response["Owner"].get("DisplayName")
            },
            "Grants": [
                {
                    "Grantee": {
                        "Type": g["Grantee"].get("Type"),
                        "ID": g["Grantee"].get("ID"),
                        "URI": g["Grantee"].get("URI")
                    },
                    "Permission": g["Permission"]
                }
                for g in response.get("Grants", [])
            ]
        }

    def get_bucket_versioning(self, bucket: str) -> str:
        response = self._client.get_bucket_versioning(Bucket=bucket)
        return response.get("Status", "Suspended")

    def enable_bucket_versioning(self, bucket: str):
        self._client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})

    def suspend_bucket_versioning(self, bucket: str):
        self._client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Suspended"})

    def generate_presigned_url(self, bucket: str, key: str, expires_in: int = 3600, method: str = "GET") -> str:
        return self._client.generate_presigned_url(
            ClientMethod=f"get_object" if method == "GET" else f"put_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in
        )
