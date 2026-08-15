"""Typed models for the SharePoint integration boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional


@dataclass(frozen=True)
class SharePointSite:
    id: str
    name: Optional[str] = None
    display_name: Optional[str] = None
    web_url: Optional[str] = None
    description: Optional[str] = None
    hostname: Optional[str] = None

    @classmethod
    def from_graph(cls, payload: Mapping[str, Any]) -> "SharePointSite":
        return cls(
            id=str(payload["id"]),
            name=payload.get("name"),
            display_name=payload.get("displayName"),
            web_url=payload.get("webUrl"),
            description=payload.get("description"),
            hostname=payload.get("siteCollection", {}).get("hostname"),
        )


@dataclass(frozen=True)
class SharePointDrive:
    id: str
    name: Optional[str] = None
    web_url: Optional[str] = None
    drive_type: Optional[str] = None

    @classmethod
    def from_graph(cls, payload: Mapping[str, Any]) -> "SharePointDrive":
        return cls(
            id=str(payload["id"]),
            name=payload.get("name"),
            web_url=payload.get("webUrl"),
            drive_type=payload.get("driveType"),
        )


@dataclass(frozen=True)
class SharePointItem:
    id: str
    name: Optional[str] = None
    web_url: Optional[str] = None
    is_folder: bool = False
    size: Optional[int] = None
    mime_type: Optional[str] = None
    parent_path: Optional[str] = None
    last_modified: Optional[str] = None
    created: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_graph(cls, payload: Mapping[str, Any]) -> "SharePointItem":
        file_data = payload.get("file") or {}
        folder_data = payload.get("folder")
        parent = payload.get("parentReference") or {}

        return cls(
            id=str(payload["id"]),
            name=payload.get("name"),
            web_url=payload.get("webUrl"),
            is_folder=folder_data is not None,
            size=payload.get("size"),
            mime_type=(file_data.get("mimeType") if file_data else None),
            parent_path=parent.get("path"),
            last_modified=payload.get("lastModifiedDateTime"),
            created=payload.get("createdDateTime"),
            metadata=dict(payload),
        )


@dataclass(frozen=True)
class SharePointConnectionStatus:
    connected: bool
    auth_mode: str
    tenant_id: str
    graph_base_url: str
    user_id: Optional[str] = None
    user_principal_name: Optional[str] = None
    scopes: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass(frozen=True)
class SharePointCapabilities:
    read_sites: bool = True
    read_drives: bool = True
    read_files: bool = True
    download_files: bool = True
    search_files: bool = True
    write_files: bool = False

    def as_dict(self) -> Dict[str, bool]:
        return {
            "read_sites": self.read_sites,
            "read_drives": self.read_drives,
            "read_files": self.read_files,
            "download_files": self.download_files,
            "search_files": self.search_files,
            "write_files": self.write_files,
        }
