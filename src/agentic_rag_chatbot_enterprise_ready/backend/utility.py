"""Compatibility helpers retained for the original Chainlit UI."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from azure.storage.blob import BlobSasPermissions, generate_blob_sas


def generate_blob_sas_url(
    account_name: str,
    account_key: str,
    container_name: str,
    blob_name: str,
    expiry_hours: int = 1,
) -> str:
    if not all((account_name, account_key, container_name, blob_name)):
        raise ValueError("account_name, account_key, container_name and blob_name are required")
    token = generate_blob_sas(
        account_name=account_name,
        container_name=container_name,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(hours=expiry_hours),
    )
    return f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}?{token}"
