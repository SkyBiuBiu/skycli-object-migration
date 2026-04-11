from typing import Dict, List, Optional, Any
from .skyclient import SkyClient


class SkyACL:
    PERMISSIONS = ["READ", "WRITE", "READ_ACP", "WRITE_ACP", "FULL_CONTROL"]
    CANONICAL_USER_PREFIX = "https://s3.amazonaws.com/docs_static/2014-01-01-RightAmazonS3.html#canonical-user-id"
    ALL_USERS_URI = "https://acs.amazonaws.com/groups/global/AllUsers"
    AUTHENTICATED_USERS_URI = "https://acs.amazonaws.com/groups/global/AuthenticatedUsers"
    LOG_DELIVERY_URI = "https://acs.amazonaws.com/groups/s3/LogDelivery"

    def __init__(self, client: SkyClient):
        self.client = client

    def get(self, bucket: str, key: Optional[str] = None, version_id: Optional[str] = None) -> Dict:
        if key:
            return self.client.get_object_acl(bucket, key, version_id)
        else:
            return self.client.get_bucket_acl(bucket)

    def set(
        self,
        bucket: str,
        key: Optional[str] = None,
        acl: Optional[str] = None,
        grant_read: Optional[str] = None,
        grant_full_control: Optional[str] = None,
        grant_write: Optional[str] = None,
        grant_read_acp: Optional[str] = None,
        grant_write_acp: Optional[str] = None,
        owner_id: Optional[str] = None,
        owner_display_name: Optional[str] = None,
        grants: Optional[List[Dict]] = None,
        version_id: Optional[str] = None
    ):
        kwargs = {"Bucket": bucket}

        if key:
            kwargs["Key"] = key
        if version_id:
            kwargs["VersionId"] = version_id

        if acl:
            kwargs["ACL"] = acl
            self._set_acl_simple(**kwargs)
            return

        access_control_policy = {
            "Grants": [],
            "Owner": {}
        }

        if owner_id:
            access_control_policy["Owner"]["ID"] = owner_id
            if owner_display_name:
                access_control_policy["Owner"]["DisplayName"] = owner_display_name

        grant_list = []

        if grants:
            for g in grants:
                grant_list.append({
                    "Grantee": g["Grantee"],
                    "Permission": g["Permission"]
                })

        if grant_read:
            grant_list.append({
                "Grantee": {"Type": "Group", "URI": self.ALL_USERS_URI},
                "Permission": "READ"
            })

        if grant_write:
            grant_list.append({
                "Grantee": {"Type": "Group", "URI": self.ALL_USERS_URI},
                "Permission": "WRITE"
            })

        if grant_full_control:
            grant_list.append({
                "Grantee": {"Type": "Group", "URI": self.ALL_USERS_URI},
                "Permission": "FULL_CONTROL"
            })

        if grant_read_acp:
            grant_list.append({
                "Grantee": {"Type": "Group", "URI": self.AUTHENTICATED_USERS_URI},
                "Permission": "READ_ACP"
            })

        if grant_write_acp:
            grant_list.append({
                "Grantee": {"Type": "Group", "URI": self.AUTHENTICATED_USERS_URI},
                "Permission": "WRITE_ACP"
            })

        access_control_policy["Grants"] = grant_list
        kwargs["AccessControlPolicy"] = access_control_policy

        self._set_acl_policy(**kwargs)

    def _set_acl_simple(self, **kwargs):
        if "Key" in kwargs:
            self.client._client.put_object_acl(**kwargs)
        else:
            self.client._client.put_bucket_acl(**kwargs)

    def _set_acl_policy(self, **kwargs):
        if "Key" in kwargs:
            self.client._client.put_object_acl(**kwargs)
        else:
            self.client._client.put_bucket_acl(**kwargs)

    def copy(
        self,
        source_bucket: str,
        source_key: str,
        target_bucket: str,
        target_key: str,
        source_version_id: Optional[str] = None
    ):
        source_acl = self.get(source_bucket, source_key, source_version_id)

        grants = []
        for grant in source_acl.get("Grants", []):
            grantee = grant.get("Grantee", {})
            permission = grant.get("Permission")

            if permission in ["READ", "WRITE", "READ_ACP", "WRITE_ACP", "FULL_CONTROL"]:
                grantee_type = grantee.get("Type")
                grantee_id = grantee.get("ID")
                grantee_uri = grantee.get("URI")

                if grantee_type == "CanonicalUser" and grantee_id:
                    grants.append({
                        "Grantee": {"Type": "CanonicalUser", "ID": grantee_id, "DisplayName": grantee.get("DisplayName")},
                        "Permission": permission
                    })
                elif grantee_type == "Group" and grantee_uri:
                    grants.append({
                        "Grantee": {"Type": "Group", "URI": grantee_uri},
                        "Permission": permission
                    })
                elif grantee_type == "AmazonCustomerByEmail" and grantee_id:
                    grants.append({
                        "Grantee": {"Type": "AmazonCustomerByEmail", "EmailAddress": grantee_id},
                        "Permission": permission
                    })

        owner = source_acl.get("Owner", {})

        access_control_policy = {
            "Grants": grants,
            "Owner": {
                "ID": owner.get("ID", ""),
                "DisplayName": owner.get("DisplayName", "")
            }
        }

        kwargs = {
            "Bucket": target_bucket,
            "Key": target_key,
            "AccessControlPolicy": access_control_policy
        }

        self.client._client.put_object_acl(**kwargs)

    def compare(self, acl1: Dict, acl2: Dict) -> Dict:
        owner1 = acl1.get("Owner", {})
        owner2 = acl2.get("Owner", {})

        grants1 = acl1.get("Grants", [])
        grants2 = acl2.get("Grants", [])

        owner_match = owner1.get("ID") == owner2.get("ID")

        grants1_sorted = sorted(grants1, key=lambda x: (x.get("Grantee", {}).get("URI", ""), x.get("Permission", "")))
        grants2_sorted = sorted(grants2, key=lambda x: (x.get("Grantee", {}).get("URI", ""), x.get("Permission", "")))

        grants_match = len(grants1_sorted) == len(grants2_sorted)

        if grants_match:
            for g1, g2 in zip(grants1_sorted, grants2_sorted):
                if g1.get("Permission") != g2.get("Permission"):
                    grants_match = False
                    break
                grantee1 = g1.get("Grantee", {})
                grantee2 = g2.get("Grantee", {})
                if grantee1.get("URI") != grantee2.get("URI") and grantee1.get("ID") != grantee2.get("ID"):
                    grants_match = False
                    break

        return {
            "match": owner_match and grants_match,
            "owner_match": owner_match,
            "grants_match": grants_match,
            "owner1": owner1,
            "owner2": owner2,
            "grants1": grants1,
            "grants2": grants2
        }

    def batch_copy(
        self,
        source_bucket: str,
        source_keys: List[str],
        target_bucket: str,
        target_prefix: str = "",
        source_version_ids: Optional[Dict[str, str]] = None
    ):
        results = []
        for source_key in source_keys:
            try:
                target_key = target_prefix + source_key.split("/")[-1] if target_prefix else source_key
                version_id = source_version_ids.get(source_key) if source_version_ids else None
                self.copy(source_bucket, source_key, target_bucket, target_key, version_id)
                results.append({"key": source_key, "success": True})
            except Exception as e:
                results.append({"key": source_key, "success": False, "error": str(e)})
        return results

    def normalize_grantee(self, grantee: Dict) -> Dict:
        normalized = {}
        for key, value in grantee.items():
            new_key = key
            if key == "ID":
                new_key = "ID"
            elif key == "URI":
                new_key = "URI"
            elif key == "DisplayName":
                new_key = "DisplayName"
            elif key == "Type":
                new_key = "Type"
            normalized[new_key] = value
        return normalized

    def format_acl(self, acl: Dict) -> str:
        lines = []
        owner = acl.get("Owner", {})
        lines.append(f"Owner: {owner.get('ID', 'N/A')} ({owner.get('DisplayName', 'N/A')})")

        for grant in acl.get("Grants", []):
            grantee = grant.get("Grantee", {})
            permission = grant.get("Permission", "")
            if grantee.get("URI"):
                lines.append(f"  {permission}: {grantee.get('URI')}")
            elif grantee.get("ID"):
                lines.append(f"  {permission}: {grantee.get('ID')} ({grantee.get('DisplayName', '')})")
            else:
                lines.append(f"  {permission}: Unknown")

        return "\n".join(lines)
