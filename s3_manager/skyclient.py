import boto3
import botocore
import os
from botocore.config import Config
from typing import Dict, List, Optional, Any, Iterator, Callable
from datetime import datetime


class SkyClient:
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        use_path_style: bool = False,
        verify_ssl: bool = True,
        signature_version: str = "s3v4"
    ):
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.use_path_style = use_path_style
        self.verify_ssl = verify_ssl
        self.signature_version = signature_version
        self._addressing_style = "path" if use_path_style else "virtual"

        self._client = self._create_client()
        self._resource = self._create_resource()

    def _create_client_config(self, addressing_style: str = None) -> Config:
        """创建 boto3 Config 对象"""
        style = addressing_style or self._addressing_style
        return Config(
            region_name=self.region,
            signature_version=self.signature_version,
            s3={"addressing_style": style},
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=10
        )

    def _create_client(self, addressing_style: str = None):
        """Create and configure boto3 S3 client.

        Args:
            addressing_style: 可选，覆盖默认的 addressing_style
        Returns:
            boto3.client: Configured S3 client
        """
        config = self._create_client_config(addressing_style)
        return boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=config,
            verify=self.verify_ssl
        )

    def _create_resource(self, addressing_style: str = None):
        """Create and configure boto3 S3 resource.

        Args:
            addressing_style: 可选，覆盖默认的 addressing_style
        Returns:
            boto3.resource: Configured S3 resource
        """
        config = self._create_client_config(addressing_style)
        return boto3.resource(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=config,
            verify=self.verify_ssl
        )

    def _auto_detect_addressing_style(self) -> str:
        """自动检测合适的 addressing style

        尝试 virtual style，如果遇到 PathStyleDomainForbidden，
        则自动切换到 path style

        Returns:
            str: 合适的 addressing style ("virtual" 或 "path")
        """
        if self.use_path_style:
            return "path"

        try:
            response = self._client.list_buckets()
            _ = [b["Name"] for b in response.get("Buckets", [])]
            return "virtual"
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("PathStyleDomainForbidden", "PermanentRedirect"):
                return "path"
            raise
        except Exception:
            return "virtual"

    def test_connection(self) -> Dict:
        try:
            if self._addressing_style == "virtual" and not self.use_path_style:
                detected_style = self._auto_detect_addressing_style()
                if detected_style != self._addressing_style:
                    self._addressing_style = detected_style
                    self._client = self._create_client()
                    self._resource = self._create_resource()

            response = self._client.list_buckets()
            buckets = [b["Name"] for b in response.get("Buckets", [])]
            return {
                "success": True,
                "bucket_count": len(buckets),
                "buckets": buckets[:10]
            }
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code in ("PathStyleDomainForbidden", "PermanentRedirect"):
                if self._addressing_style != "path":
                    self._addressing_style = "path"
                    self._client = self._create_client()
                    self._resource = self._create_resource()
                    return self.test_connection()

            return {
                "success": False,
                "error_code": error_code,
                "error": f"[{error_code}] {error_message}"
            }
        except Exception as e:
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

        try:
            response = self._client.list_objects_v2(**kwargs)
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            raise RuntimeError(
                f"Failed to list objects in bucket '{bucket}' with prefix '{prefix}': "
                f"[{error_code}] {error_message}"
            )

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
        """Create an S3 bucket.
        
        Args:
            bucket: The name of the bucket
            region: The region to create the bucket in. If not provided, uses self.region.
                   For us-east-1, no LocationConstraint is needed.
        """
        kwargs = {"Bucket": bucket}
        # Use instance region if not provided
        bucket_region = region or self.region
        
        # Only add LocationConstraint for regions other than us-east-1
        if bucket_region and bucket_region != "us-east-1":
            kwargs["CreateBucketConfiguration"] = {"LocationConstraint": bucket_region}
        
        self._client.create_bucket(**kwargs)

    def delete_bucket(self, bucket: str):
        self._client.delete_bucket(Bucket=bucket)

    def bucket_exists(self, bucket: str) -> bool:
        try:
            self._client.head_bucket(Bucket=bucket)
            return True
        except Exception:
            return False

    def get_bucket_location(self, bucket: str) -> str:
        response = self._client.get_bucket_location(Bucket=bucket)
        return response.get("LocationConstraint") or "us-east-1"

    def get_bucket_policy(self, bucket: str) -> Optional[Dict]:
        try:
            response = self._client.get_bucket_policy(Bucket=bucket)
            import json
            return json.loads(response["Policy"])
        except Exception:
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

    def create_multipart_upload(
        self,
        bucket: str,
        key: str,
        metadata: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None,
        storage_class: str = "STANDARD",
        sse: Optional[Dict] = None
    ) -> Dict:
        kwargs = {"Bucket": bucket, "Key": key}

        if content_type:
            kwargs["ContentType"] = content_type
        if storage_class:
            kwargs["StorageClass"] = storage_class
        if metadata:
            kwargs["Metadata"] = metadata
        if sse:
            kwargs["ServerSideEncryption"] = sse.get("Algorithm", "AES256")
            if "KmsKeyId" in sse:
                kwargs["SSEKMSKeyId"] = sse["KmsKeyId"]

        response = self._client.create_multipart_upload(**kwargs)
        return {
            "UploadId": response["UploadId"],
            "Bucket": bucket,
            "Key": key
        }

    def upload_part(
        self,
        bucket: str,
        key: str,
        upload_id: str,
        part_number: int,
        data: bytes
    ) -> Dict:
        kwargs = {
            "Bucket": bucket,
            "Key": key,
            "UploadId": upload_id,
            "PartNumber": part_number,
            "Body": data
        }

        response = self._client.upload_part(**kwargs)
        return {
            "ETag": response["ETag"].strip('"') if isinstance(response["ETag"], str) else response["ETag"].decode("utf-8").strip('"'),
            "PartNumber": part_number
        }

    def complete_multipart_upload(
        self,
        bucket: str,
        key: str,
        upload_id: str,
        parts: List[Dict]
    ) -> Dict:
        parts_list = [
            {"PartNumber": p["PartNumber"], "ETag": p["ETag"]}
            for p in sorted(parts, key=lambda x: x["PartNumber"])
        ]

        kwargs = {
            "Bucket": bucket,
            "Key": key,
            "UploadId": upload_id,
            "MultipartUpload": {"Parts": parts_list}
        }

        response = self._client.complete_multipart_upload(**kwargs)
        return {
            "Location": response.get("Location"),
            "Bucket": response.get("Bucket"),
            "Key": response.get("Key"),
            "ETag": response.get("ETag", "").strip('"')
        }

    def abort_multipart_upload(self, bucket: str, key: str, upload_id: str) -> bool:
        self._client.abort_multipart_upload(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id
        )
        return True

    def list_parts(self, bucket: str, key: str, upload_id: str) -> List[Dict]:
        response = self._client.list_parts(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id
        )
        return [
            {
                "PartNumber": p["PartNumber"],
                "ETag": p["ETag"].strip('"') if isinstance(p["ETag"], str) else p["ETag"].decode("utf-8").strip('"'),
                "Size": p["Size"]
            }
            for p in response.get("Parts", [])
        ]

    def list_multipart_uploads(self, bucket: str, prefix: str = "") -> List[Dict]:
        kwargs = {"Bucket": bucket}
        if prefix:
            kwargs["Prefix"] = prefix

        response = self._client.list_multipart_uploads(**kwargs)
        uploads = []
        for upload in response.get("Uploads", []):
            uploads.append({
                "Key": upload["Key"],
                "UploadId": upload["UploadId"],
                "Initiated": upload.get("Initiated"),
                "StorageClass": upload.get("StorageClass", "STANDARD")
            })
        return uploads

    def multipart_upload_file(
        self,
        bucket: str,
        key: str,
        file_path: str,
        part_size: int = 8 * 1024 * 1024,
        metadata: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None,
        storage_class: str = "STANDARD",
        sse: Optional[Dict] = None,
        cache_control: Optional[str] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        file_size = os.path.getsize(file_path)

        extra_args = {}
        if content_type:
            extra_args["content_type"] = content_type
        if cache_control:
            extra_args["cache_control"] = cache_control

        if file_size <= part_size:
            return self.upload_file(bucket, key, file_path, metadata, content_type, storage_class, extra_args=extra_args if extra_args else None)

        init_response = self.create_multipart_upload(
            bucket, key, metadata, content_type, storage_class, sse
        )
        upload_id = init_response["UploadId"]

        parts = []
        uploaded_bytes = 0

        try:
            with open(file_path, "rb") as f:
                part_number = 1
                while True:
                    data = f.read(part_size)
                    if not data:
                        break

                    part_info = self.upload_part(bucket, key, upload_id, part_number, data)
                    parts.append({
                        "PartNumber": part_number,
                        "ETag": part_info["ETag"]
                    })

                    uploaded_bytes += len(data)
                    if progress_callback:
                        progress_callback(uploaded_bytes, file_size)

                    part_number += 1

            result = self.complete_multipart_upload(bucket, key, upload_id, parts)
            result["Parts"] = len(parts)
            return result

        except Exception as e:
            self.abort_multipart_upload(bucket, key, upload_id)
            raise e
