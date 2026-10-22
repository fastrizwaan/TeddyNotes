# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Any

@dataclass
class Note:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Untitled Note"
    content_html: str = ""
    content_markdown: str = ""
    excerpt: str = ""
    category: str = ""
    tags: List[str] = field(default_factory=list)
    is_pinned: bool = False
    is_archived: bool = False
    is_trashed: bool = False
    has_todo: bool = False
    has_list: bool = False
    has_link: bool = False
    is_locked: bool = False
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    preview_content: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "content_html": self.content_html,
            "content_markdown": self.content_markdown,
            "excerpt": self.excerpt,
            "category": self.category,
            "tags": self.tags,
            "is_pinned": self.is_pinned,
            "is_archived": self.is_archived,
            "is_trashed": self.is_trashed,
            "has_todo": self.has_todo,
            "has_list": self.has_list,
            "has_link": self.has_link,
            "is_locked": self.is_locked,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: Any) -> "Note":
        keys = row.keys()
        tags_raw = row["tags"] if "tags" in keys else "[]"
        try:
            tags = json.loads(tags_raw) if tags_raw else []
        except Exception:
            tags = [t.strip() for t in str(tags_raw).split(",") if t.strip()]

        category = row["category"] if "category" in keys and row["category"] else ""
        content_md = row["content_markdown"] if "content_markdown" in keys and row["content_markdown"] else ""
        content_html = row["content_html"] if "content_html" in keys and row["content_html"] else ""

        return cls(
            id=str(row["id"]),
            title=row["title"] or "Untitled Note",
            content_html=content_html,
            content_markdown=content_md,
            excerpt=row["excerpt"] if "excerpt" in keys and row["excerpt"] else "",
            category=category,
            tags=tags,
            is_pinned=bool(row["is_pinned"]),
            is_archived=bool(row["is_archived"]),
            is_trashed=bool(row["is_trashed"]),
            has_todo=bool(row["has_todo"]),
            has_list=bool(row["has_list"]) if "has_list" in keys else False,
            has_link=bool(row["has_link"]) if "has_link" in keys else False,
            is_locked=bool(row["is_locked"]) if "is_locked" in keys else False,
            created_at=float(row["created_at"] or time.time()),
            updated_at=float(row["updated_at"] or time.time()),
            preview_content=row["preview_content"] if "preview_content" in keys and row["preview_content"] else "",
        )

@dataclass
class Category:
    id: str
    name: str
    icon: str = "folder-symbolic"
    color: str = ""
    count: int = 0
    is_system: bool = False
    sort_order: int = 0
