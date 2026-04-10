from typing import Dict, List, Optional, Any
from .skyclient import SkyClient


class SkyMetadata:
    def __init__(self, client: SkyClient):
        self.client = client

    def get(self, bucket: str, key: str, version_id: Optional[str] = None) -> Dict:
        info = self.client.head_object(bucket, key, version_id)
        return {
            "ContentLength": info.get("ContentLength"),
            "ContentType": info.get("ContentType"),
            "ContentMD5": info.get("ContentMD5"),
            "LastModified": info.get("LastModified"),
            "ETag": info.get("ETag"),
            "StorageClass": info.get("StorageClass"),
            "Metadata": info.get("Metadata", {}),
            "CacheControl": info.get("CacheControl"),
            "Expires": info.get("Expires")
        }

    def set(
        self,
        bucket: str,
        key: str,
        metadata: Dict[str, str],
        operation: str = "REPLACE",
        version_id: Optional[str] = None
    ):
        if operation == "COPY":
            current = self.get(bucket, key, version_id)
            combined = {**current.get("Metadata", {}), **metadata}
            metadata = combined

        self.client.copy_object(
            source_bucket=bucket,
            source_key=key,
            target_bucket=bucket,
            target_key=key,
            metadata=metadata,
            metadata_directive="REPLACE",
            source_version_id=version_id
        )

    def compare(self, metadata1: Dict, metadata2: Dict, fields: Optional[List[str]] = None) -> Dict:
        if fields is None:
            fields = ["ContentType", "ContentLength", "ContentMD5", "CacheControl", "Expires", "Metadata"]

        differences = {}
        for field in fields:
            if field == "Metadata":
                val1 = metadata1.get("Metadata", {})
                val2 = metadata2.get("Metadata", {})
                if val1 != val2:
                    differences[field] = {
                        "source": val1,
                        "target": val2,
                        "match": False
                    }
            else:
                val1 = metadata1.get(field)
                val2 = metadata2.get(field)
                if val1 != val2:
                    differences[field] = {
                        "source": val1,
                        "target": val2,
                        "match": False
                    }
                else:
                    differences[field] = {
                        "source": val1,
                        "target": val2,
                        "match": True
                    }

        all_match = all(d.get("match", False) for d in differences.values())
        return {
            "match": all_match,
            "differences": differences
        }

    def copy(
        self,
        source_bucket: str,
        source_key: str,
        target_bucket: str,
        target_key: str,
        preserve: bool = True,
        metadata: Optional[Dict[str, str]] = None
    ):
        if preserve:
            metadata_directive = "COPY"
        else:
            metadata_directive = "REPLACE"

        return self.client.copy_object(
            source_bucket=source_bucket,
            source_key=source_key,
            target_bucket=target_bucket,
            target_key=target_key,
            metadata=metadata,
            metadata_directive=metadata_directive
        )

    def list_for_prefix(self, bucket: str, prefix: str = "") -> List[Dict]:
        results = []
        for obj in self.client.list_objects_all(bucket, prefix):
            info = self.get(bucket, obj["Key"])
            results.append({
                "Key": obj["Key"],
                **info
            })
        return results

    def update_from_template(self, bucket: str, key: str, template: Dict[str, str], version_id: Optional[str] = None):
        self.set(bucket, key, template, operation="COPY", version_id=version_id)

    def batch_update(
        self,
        bucket: str,
        keys: List[str],
        metadata: Dict[str, str],
        operation: str = "REPLACE"
    ):
        results = []
        for key in keys:
            try:
                self.set(bucket, key, metadata, operation)
                results.append({"key": key, "success": True})
            except Exception as e:
                results.append({"key": key, "success": False, "error": str(e)})
        return results


STANDARD_FIELDS = [
    "ContentType",
    "ContentLength",
    "ContentMD5",
    "CacheControl",
    "Expires",
    "LastModified",
    "ETag",
    "StorageClass"
]


def normalize_metadata(metadata: Dict) -> Dict:
    normalized = {}
    for key, value in metadata.items():
        new_key = key
        if key.lower().startswith("x-amz-meta-"):
            new_key = key[11:]
        elif key.lower() == "content-length":
            new_key = "ContentLength"
        elif key.lower() == "content-type":
            new_key = "ContentType"
        elif key.lower() == "content-md5":
            new_key = "ContentMD5"
        elif key.lower() == "last-modified":
            new_key = "LastModified"
        elif key.lower() == "etag":
            new_key = "ETag"
        elif key.lower() == "storage-class":
            new_key = "StorageClass"
        elif key.lower() == "cache-control":
            new_key = "CacheControl"
        elif key.lower() == "expires":
            new_key = "Expires"
        normalized[new_key] = value
    return normalized
