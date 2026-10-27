# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import base64
import hashlib
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import urllib.parse
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from gi.repository import GLib

HAS_CRYPTOGRAPHY = None  # Lazy-checked on first use

from teddynotes.models import Note, Category
from teddynotes.markdown_utils import (
    extract_title_and_excerpt,
    extract_tags,
    extract_categories,
    extract_table_data,
    check_has_todo,
    check_has_list,
    check_has_link,
    markdown_to_html,
    html_to_markdown,
    is_untitled_title,
    RE_TAG_EXTRACT,
    RE_CAT_HASH,
)

class NoteDatabase:
    """High-performance SQLite Database manager for Teddy Notes."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            data_dir = Path(GLib.get_user_data_dir()) / "teddynotes"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = data_dir / "teddynotes.db"
            old_db_path = Path(GLib.get_user_data_dir()) / "stilonotes" / "stilonotes.db"
            if not self.db_path.exists() and old_db_path.exists():
                try:
                    import shutil
                    shutil.copy2(old_db_path, self.db_path)
                except Exception as e:
                    print(f"Could not copy old stilonotes.db: {e}")

        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._change_listeners = []
        self._session_password: Optional[str] = None

        self._init_db()

    def add_change_listener(self, callback):
        """Register a callback for database change notifications: callback(event_type, data, sender)."""
        if callback not in self._change_listeners:
            self._change_listeners.append(callback)

    def remove_change_listener(self, callback):
        """Unregister a database change callback."""
        if callback in self._change_listeners:
            self._change_listeners.remove(callback)

    def _notify_change(self, event_type: str, data: Optional[Dict[str, Any]] = None, sender: Any = None):
        """Notify all registered listeners on the GLib main loop."""
        if not self._change_listeners:
            return
        payload = data or {}
        listeners = list(self._change_listeners)

        def dispatch():
            for cb in listeners:
                try:
                    cb(event_type, payload, sender)
                except Exception as e:
                    print(f"Error in db change listener for {event_type}:", e)
            return False

        try:
            GLib.idle_add(dispatch)
        except Exception:
            dispatch()

    def _register_functions(self, conn: sqlite3.Connection):
        """Register custom SQLite functions for fast content classification."""
        conn.create_function(
            "has_todo_fn", 2,
            lambda md, html: 1 if (check_has_todo(md) or check_has_todo(html)) else 0
        )
        conn.create_function(
            "has_list_fn", 2,
            lambda md, html: 1 if (check_has_list(md) or check_has_list(html)) else 0
        )
        conn.create_function(
            "has_link_fn", 2,
            lambda md, html: 1 if (check_has_link(md) or check_has_link(html)) else 0
        )

    @contextmanager
    def get_connection(self):
        """Thread-safe context manager for the shared SQLite connection.

        On an exception propagating out of the caller's block any dangling
        (uncommitted) transaction is rolled back, so a failed write cannot
        leave the connection in a half-open state that a later unrelated
        ``commit()`` would silently apply.
        """
        with self._lock:
            if self._conn is None:
                is_mem = str(self.db_path) == ":memory:"
                conn_path = ":memory:" if is_mem else str(self.db_path)
                conn = sqlite3.connect(conn_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                self._register_functions(conn)

                # Performance tuning pragmas
                if not is_mem:
                    conn.execute("PRAGMA journal_mode = WAL")
                    conn.execute("PRAGMA synchronous = NORMAL")
                    conn.execute("PRAGMA temp_store = MEMORY")
                    conn.execute("PRAGMA cache_size = -64000")
                conn.execute("PRAGMA busy_timeout = 5000")
                self._conn = conn

            conn = self._conn
            try:
                yield conn
            except BaseException:
                if conn.in_transaction:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                raise

    @contextmanager
    def _write_transaction(self):
        """Lock-guarded write transaction that commits on success and rolls back on error.

        Unlike ``get_connection`` (which only guards access to the shared
        connection), this commits exactly once on success. Any exception raised
        part-way through the write is rolled back by ``get_connection`` and
        re-raised, so the connection is never left holding a partially applied
        transaction.
        """
        with self.get_connection() as conn:
            yield conn
            conn.commit()

    def close(self):
        """Cleanly close database connection and free resources."""
        with self._lock:
            self._change_listeners.clear()
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

    def __del__(self):
        self.close()

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Notes table - content_markdown is the single source of truth
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                title TEXT,
                content_html TEXT,
                content_markdown TEXT,
                excerpt TEXT,
                category TEXT DEFAULT '',
                tags TEXT,
                is_pinned INTEGER DEFAULT 0,
                is_archived INTEGER DEFAULT 0,
                is_trashed INTEGER DEFAULT 0,
                has_todo INTEGER DEFAULT 0,
                has_list INTEGER DEFAULT 0,
                has_link INTEGER DEFAULT 0,
                is_locked INTEGER DEFAULT 0,
                created_at REAL,
                updated_at REAL
            )
            """)

            # Ensure is_locked, has_list, and has_link columns exist for existing databases
            cursor.execute("PRAGMA table_info(notes)")
            existing_cols = [col["name"] for col in cursor.fetchall()]
            if "is_locked" not in existing_cols:
                cursor.execute("ALTER TABLE notes ADD COLUMN is_locked INTEGER DEFAULT 0")
            if "has_list" not in existing_cols:
                cursor.execute("ALTER TABLE notes ADD COLUMN has_list INTEGER DEFAULT 0")
            if "has_link" not in existing_cols:
                cursor.execute("ALTER TABLE notes ADD COLUMN has_link INTEGER DEFAULT 0")

            # Attachments table for storing images and media as binary blobs
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                id TEXT PRIMARY KEY,
                note_id TEXT,
                filename TEXT,
                mime_type TEXT,
                data BLOB,
                size_bytes INTEGER,
                created_at REAL
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_note ON attachments (note_id)")

            # Categories table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE,
                icon TEXT DEFAULT 'folder-symbolic',
                color TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0,
                created_at REAL
            )
            """)

            # Ensure sort_order column exists for existing databases
            cursor.execute("PRAGMA table_info(categories)")
            cat_cols = [col["name"] for col in cursor.fetchall()]
            if "sort_order" not in cat_cols:
                cursor.execute("ALTER TABLE categories ADD COLUMN sort_order INTEGER DEFAULT 0")

            # App settings table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """)

            # Indices for instant lookups and sorting
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes (updated_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_trashed ON notes (is_trashed)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_pinned ON notes (is_pinned)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_category ON notes (category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_trashed_pinned_updated ON notes (is_trashed, is_pinned, updated_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_trashed_cat ON notes (is_trashed, category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_locked ON notes (is_locked)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_trashed_locked_updated ON notes (is_trashed, is_locked, updated_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_has_list ON notes (has_list)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notes_has_link ON notes (has_link)")

            # Migrate legacy notes if content_markdown is empty but content_html exists
            cursor.execute("""
            SELECT id, content_html FROM notes
            WHERE (content_markdown IS NULL OR content_markdown = '')
              AND (content_html IS NOT NULL AND content_html != '')
            """)
            legacy_notes = cursor.fetchall()
            for r in legacy_notes:
                md = html_to_markdown(r["content_html"])
                cursor.execute("UPDATE notes SET content_markdown = ? WHERE id = ?", (md, r["id"]))

            # Ensure notes with checklist items have has_todo set to 1
            cursor.execute("SELECT id, content_markdown, content_html, has_todo FROM notes WHERE has_todo = 0 AND is_trashed = 0")
            for r in cursor.fetchall():
                if check_has_todo(r["content_markdown"]) or check_has_todo(r["content_html"]):
                    cursor.execute("UPDATE notes SET has_todo = 1 WHERE id = ?", (r["id"],))

            # Ensure notes with list items have has_list set to 1
            cursor.execute("SELECT id, content_markdown, content_html FROM notes WHERE has_list IS NULL OR has_list = 0")
            for r in cursor.fetchall():
                if check_has_list(r["content_markdown"]) or check_has_list(r["content_html"]):
                    cursor.execute("UPDATE notes SET has_list = 1 WHERE id = ?", (r["id"],))

            # Ensure notes with links have has_link set to 1
            cursor.execute("SELECT id, content_markdown, content_html FROM notes WHERE has_link IS NULL OR has_link = 0")
            for r in cursor.fetchall():
                if check_has_link(r["content_markdown"]) or check_has_link(r["content_html"]):
                    cursor.execute("UPDATE notes SET has_link = 1 WHERE id = ?", (r["id"],))

            # Ensure uncategorized is never in categories table or notes category field
            cursor.execute("DELETE FROM categories WHERE LOWER(name) = 'uncategorized'")
            cursor.execute("UPDATE notes SET category = '' WHERE LOWER(category) = 'uncategorized'")

            conn.commit()

            # Seed initial sample note if empty
            cursor.execute("SELECT COUNT(*) as cnt FROM notes")
            if cursor.fetchone()["cnt"] == 0:
                self._seed_welcome_notes(conn)

    def _seed_welcome_notes(self, conn: sqlite3.Connection):
        """Create a delightful welcome note showcasing Teddy Notes features."""
        now = time.time()
        note_id = str(uuid.uuid4())
        title = "Welcome to Teddy Notes 🖊️"

        md_content = """# Welcome to Teddy Notes 🖊️

**Teddy Notes** brings together the clean, distraction-free **GNOME Adwaita** interface of Iotas with the dynamic **WebKit Markdown** live rendering engine!

### ✨ Key Features
- **Dynamic Markdown Parsing**: Type markdown on the fly and watch it format live!
- **Interactive Checklists**: Click checkboxes directly in the editor to mark tasks complete.
- **Fast Sidebar Organization**: Group notes by Categories or Favorites.
- **Real-time Statistics**: View word count, characters, and reading time.
- **Export Anywhere**: Export cleanly to Markdown, HTML, or Plain Text.

### 📝 Try These Quick Formatting Shortcuts
- Type `# ` for Heading 1, `## ` for Heading 2, or `### ` for Heading 3
- Type `- [ ] ` to start an interactive checklist
- Type `* ` or `- ` for bullet lists, `1. ` for numbered lists
- Type `> ` for blockquotes
- Type `---` on an empty line for a divider
- Type `**bold**`, `*italic*`, `==highlight==`, or `~~strikethrough~~`

### ☑️ Your First Checklist
- [x] Launch Teddy Notes
- [ ] Try typing a new thought below
- [ ] Toggle dark and light mode
- [ ] Create a custom category in the sidebar

Enjoy writing with Teddy Notes!
"""
        html_content = markdown_to_html(md_content)
        title, excerpt = extract_title_and_excerpt(md_content, html_content)
        tags = json.dumps(["welcome", "notes"])

        conn.execute("""
        INSERT INTO notes (
            id, title, content_html, content_markdown, excerpt, category,
            tags, is_pinned, is_archived, is_trashed, has_todo, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            note_id, title, html_content, md_content, excerpt, "Personal",
            tags, 1, 0, 0, 1, now, now
        ))

        # Insert sample category
        conn.execute("INSERT OR IGNORE INTO categories (id, name, icon, created_at) VALUES (?, ?, ?, ?)",
                     (str(uuid.uuid4()), "Personal", "user-home-symbolic", now))
        conn.execute("INSERT OR IGNORE INTO categories (id, name, icon, created_at) VALUES (?, ?, ?, ?)",
                     (str(uuid.uuid4()), "Work", "x-office-document-symbolic", now))

        conn.commit()

    def get_notes(
        self,
        filter_type: str = "all",
        category_name: str = "",
        tag_name: str = "",
        search_query: str = ""
    ) -> List[Note]:
        """Fetch notes for list display without loading massive content fields into memory."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Lightweight: select only metadata needed for list rendering (no content).
            # Locked note bodies are decrypted lazily in get_note().
            query = """
            SELECT id, title, excerpt, category, tags, is_pinned, is_archived, is_trashed,
                   has_todo, has_list, has_link, is_locked, created_at, updated_at,
                   CASE WHEN is_locked = 0 THEN
                       substr(COALESCE(NULLIF(content_markdown, ''), content_html, ''), 1, 1024)
                   ELSE '' END AS preview_content
            FROM notes WHERE 1=1
            """
            params: List[Any] = []

            # Trash filtering
            if filter_type == "trash":
                query += " AND is_trashed = 1"
            else:
                query += " AND is_trashed = 0"

            # Private / Locked filtering
            if filter_type in ("private", "locked"):
                query += " AND is_locked = 1"
            elif filter_type != "trash":
                # Non-private views exclude locked private notes
                query += " AND is_locked = 0"

            # Category / Tab filters
            if filter_type in ("pinned", "favorites"):
                query += " AND is_pinned = 1"
            elif filter_type in ("private", "locked"):
                pass  # already filtered by is_locked = 1
            elif filter_type in ("todo", "todos"):
                query += " AND has_todo = 1"
            elif filter_type in ("list", "lists"):
                query += " AND has_list = 1"
            elif filter_type in ("linked", "link", "links"):
                query += " AND has_link = 1"
            elif filter_type in ("recent", "recents"):
                recent_cutoff = time.time() - (7 * 86400)
                query += " AND updated_at >= ?"
                params.append(recent_cutoff)
            elif filter_type == "uncategorized":
                query += " AND (category = '' OR category IS NULL)"
            elif filter_type == "category" and category_name:
                query += " AND (category = ? OR category LIKE ?)"
                params.append(category_name)
                params.append(category_name + "/%")
            elif (filter_type == "tag" and (category_name or tag_name)) or tag_name:
                t = (tag_name or category_name).strip().lstrip("#").lower()
                query += " AND (tags LIKE ? OR content_markdown LIKE ?)"
                params.append(f'%"{t}"%')
                params.append(f'%#{t}%')

            # Search query
            if search_query:
                q = f"%{search_query.strip()}%"
                query += " AND (title LIKE ? OR excerpt LIKE ? OR content_markdown LIKE ?)"
                params.extend([q, q, q])

            # In All Notes, Private, Recent, Todos, Lists, and Linked, sort strictly by updated_at descending; for others, pinned notes appear first
            if filter_type in ("all", "recent", "recents", "private", "locked", "todo", "todos", "list", "lists", "linked", "link", "links") or not filter_type:
                query += " ORDER BY updated_at DESC"
            else:
                query += " ORDER BY is_pinned DESC, updated_at DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [Note.from_row(row) for row in rows]

    def get_note(self, note_id: str) -> Optional[Note]:
        """Retrieve single note by ID with full content (Markdown as authoritative source)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()
            if not row:
                return None

            note = Note.from_row(row)
            if note.is_locked and self._get_session_password():
                # Decrypt the body before handing it to the editor. The decrypted
                # plaintext is returned to the caller; it is never written back
                # unless the note is saved or duplicated.
                try:
                    note.content_markdown = self._decrypt_blob(note.content_markdown, self._get_session_password())
                    note.content_html = markdown_to_html(note.content_markdown)
                except Exception:
                    # Body not encrypted yet (created before a password was set);
                    # treat as plaintext.
                    pass
            # Ensure content_html is dynamically synchronized with canonical Markdown
            if note.content_markdown and not note.content_html:
                note.content_html = markdown_to_html(note.content_markdown)
            elif not note.content_markdown and note.content_html:
                note.content_markdown = html_to_markdown(note.content_html)
            return note

    def save_note(
        self,
        note_id: str,
        title: Optional[str] = None,
        content_html: Optional[str] = None,
        content_markdown: Optional[str] = None,
        excerpt: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_pinned: Optional[bool] = None,
        is_archived: Optional[bool] = None,
        is_trashed: Optional[bool] = None,
        has_todo: Optional[bool] = None,
        is_locked: Optional[bool] = None,
        sender: Any = None,
    ) -> Note:
        """Save note with Markdown as the authoritative single source of truth."""
        now = time.time()
        with self._write_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()

            if row:
                existing = Note.from_row(row)
                # Markdown is canonical
                if content_markdown is not None:
                    new_md = content_markdown
                elif content_html is not None:
                    new_md = html_to_markdown(content_html)
                else:
                    new_md = existing.content_markdown

                new_locked = int(is_locked if is_locked is not None else getattr(existing, "is_locked", 0))

                # Synchronize HTML from canonical markdown
                new_html = content_html if content_html is not None else markdown_to_html(new_md)

                # Encrypt the body of a locked note at rest when a master password
                # is configured. content_markdown is the canonical field, so the
                # encrypted blob is stored there; content_html is the rendered
                # rendering of the decrypted plaintext and is stored as well.
                private_password = self._get_session_password()
                if new_locked and private_password:
                    try:
                        salt = secrets.token_bytes(16)
                        new_md = self._encrypt_blob(new_md, salt, private_password)
                        new_html = new_md  # rendered body is not displayed; keep in sync
                    except Exception:
                        # Encryption failed (or body was already a valid ciphertext
                        # and we could not re-derive it): leave the note plaintext
                        # so it stays readable by the app. It will be encrypted on
                        # the next save while locked, or once a password is set.
                        pass

                # Avoid redundant regex extraction when title/excerpt already supplied
                if title is not None and not is_untitled_title(title) and excerpt is not None:
                    new_title = title
                    new_excerpt = excerpt
                else:
                    extracted_title, extracted_excerpt = extract_title_and_excerpt(new_md, new_html)
                    new_title = title if (title is not None and not is_untitled_title(title)) else (
                        extracted_title if (extracted_title and not is_untitled_title(extracted_title))
                        else (title or existing.title or self.get_next_untitled_title())
                    )
                    new_excerpt = excerpt if excerpt is not None else extracted_excerpt

                extracted_tags = extract_tags(new_md or new_html)
                if tags is not None:
                    new_tags = list(dict.fromkeys(tags + extracted_tags))
                else:
                    new_tags = extracted_tags

                extracted_cats = extract_categories(new_md or new_html)
                if category is not None:
                    new_category = category.strip()
                elif extracted_cats:
                    new_category = extracted_cats[0].strip()
                    if new_category.lower() != "uncategorized":
                        self._create_category_sync(conn, new_category)
                else:
                    new_category = (existing.category or "").strip()
                if new_category.lower() == "uncategorized":
                    new_category = ""
                new_pinned = int(is_pinned if is_pinned is not None else existing.is_pinned)
                new_archived = int(is_archived if is_archived is not None else existing.is_archived)
                new_trashed = int(is_trashed if is_trashed is not None else existing.is_trashed)
                if has_todo or check_has_todo(new_md) or check_has_todo(new_html):
                    new_todo = 1
                else:
                    new_todo = 0
                new_has_list = 1 if (check_has_list(new_md) or check_has_list(new_html)) else 0
                new_has_link = 1 if (check_has_link(new_md) or check_has_link(new_html)) else 0

                cursor.execute("""
                UPDATE notes SET
                    title = ?,
                    content_html = ?,
                    content_markdown = ?,
                    excerpt = ?,
                    category = ?,
                    tags = ?,
                    is_pinned = ?,
                    is_archived = ?,
                    is_trashed = ?,
                    has_todo = ?,
                    has_list = ?,
                    has_link = ?,
                    is_locked = ?,
                    updated_at = ?
                WHERE id = ?
                """, (
                    new_title,
                    new_html,
                    new_md,
                    new_excerpt,
                    new_category,
                    json.dumps(new_tags),
                    new_pinned,
                    new_archived,
                    new_trashed,
                    new_todo,
                    new_has_list,
                    new_has_link,
                    new_locked,
                    now,
                    note_id
                ))
            else:
                if content_markdown is not None:
                    new_md = content_markdown
                elif content_html:
                    new_md = html_to_markdown(content_html)
                else:
                    new_md = ""

                new_locked = int(is_locked or 0)

                new_html = content_html or markdown_to_html(new_md)

                # Encrypt the body of a locked note at rest when a master password
                # is configured. content_markdown is the canonical field, so the
                # encrypted blob is stored there; content_html is the rendered
                # rendering of the decrypted plaintext and is stored as well.
                private_password = self._get_session_password()
                if new_locked and private_password:
                    try:
                        salt = secrets.token_bytes(16)
                        new_md = self._encrypt_blob(new_md, salt, private_password)
                        new_html = new_md  # rendered body is not displayed; keep in sync
                    except Exception:
                        # Encryption failed (or body was already a valid ciphertext
                        # and we could not re-derive it): leave the note plaintext
                        # so it stays readable by the app. It will be encrypted on
                        # the next save while locked, or once a password is set.
                        pass

                if title and not is_untitled_title(title) and excerpt is not None:
                    new_title = title
                    new_excerpt = excerpt
                else:
                    extracted_title, extracted_excerpt = extract_title_and_excerpt(new_md, new_html)
                    new_title = title if (title and not is_untitled_title(title)) else (
                        extracted_title if (extracted_title and not is_untitled_title(extracted_title))
                        else (title or self.get_next_untitled_title())
                    )
                    new_excerpt = excerpt if excerpt is not None else extracted_excerpt

                extracted_tags = extract_tags(new_md or new_html)
                if tags is not None:
                    new_tags = list(dict.fromkeys(tags + extracted_tags))
                else:
                    new_tags = extracted_tags
                new_category = (category or "").strip()
                if not new_category:
                    extracted_cats = extract_categories(new_md or new_html)
                    if extracted_cats:
                        new_category = extracted_cats[0].strip()
                        if new_category.lower() != "uncategorized":
                            self._create_category_sync(conn, new_category)
                if new_category.lower() == "uncategorized":
                    new_category = ""
                new_pinned = int(is_pinned or 0)
                new_archived = int(is_archived or 0)
                new_trashed = int(is_trashed or 0)
                if has_todo or check_has_todo(new_md) or check_has_todo(new_html):
                    new_todo = 1
                else:
                    new_todo = 0
                new_has_list = 1 if (check_has_list(new_md) or check_has_list(new_html)) else 0
                new_has_link = 1 if (check_has_link(new_md) or check_has_link(new_html)) else 0

                cursor.execute("""
                INSERT INTO notes (
                    id, title, content_html, content_markdown, excerpt, category,
                    tags, is_pinned, is_archived, is_trashed, has_todo, has_list, has_link, is_locked, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    note_id,
                    new_title,
                    new_html,
                    new_md,
                    new_excerpt,
                    new_category,
                    json.dumps(new_tags),
                    new_pinned,
                    new_archived,
                    new_trashed,
                    new_todo,
                    new_has_list,
                    new_has_link,
                    new_locked,
                    now,
                    now
                ))

            # Prune attachments no longer referenced in note content
            if new_html is not None or new_md is not None:
                referenced_att_ids = set()
                for c in (new_html or "", new_md or ""):
                    for m in re.finditer(r'attachment://([a-zA-Z0-9_\-\.\+]+)', c):
                        referenced_att_ids.add(m.group(1).split('/')[0].split('?')[0])
                    for m in re.finditer(r'attachment:([a-zA-Z0-9_\-\.\+]+)', c):
                        referenced_att_ids.add(m.group(1).split('/')[0].split('?')[0])
                if referenced_att_ids:
                    placeholders = ','.join('?' for _ in referenced_att_ids)
                    cursor.execute(
                        f"DELETE FROM attachments WHERE note_id = ? AND id NOT IN ({placeholders})",
                        [note_id] + list(referenced_att_ids)
                    )
                else:
                    cursor.execute("DELETE FROM attachments WHERE note_id = ?", (note_id,))

            conn.commit()
            saved_note = Note(
                id=note_id,
                title=new_title,
                content_html=new_html,
                content_markdown=new_md,
                excerpt=new_excerpt,
                category=new_category,
                tags=new_tags,
                is_pinned=bool(new_pinned),
                is_archived=bool(new_archived),
                is_trashed=bool(new_trashed),
                has_todo=bool(new_todo),
                has_list=bool(new_has_list),
                has_link=bool(new_has_link),
                is_locked=bool(new_locked),
                created_at=row["created_at"] if row else now,
                updated_at=now,
            )
        # Dispatch the change notification only after the transaction has
        # committed and the DB lock has been released.
        self._notify_change("note-saved", {"note_id": note_id, "note": saved_note}, sender=sender)
        return saved_note

    def get_next_untitled_title(self) -> str:
        """Generate the next unique untitled note title with a counter (e.g. Untitled Note 1, 2, 3)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT title FROM notes WHERE is_trashed = 0 AND (title = 'Untitled Note' OR title LIKE 'Untitled Note %')"
            )
            rows = cursor.fetchall()

        used_numbers = set()
        for r in rows:
            t = (r["title"] or "").strip()
            m = re.match(r"^Untitled Note\s+(\d+)$", t, re.IGNORECASE)
            if m:
                used_numbers.add(int(m.group(1)))

        num = 1
        while num in used_numbers:
            num += 1

        return f"Untitled Note {num}"

    def create_note(
        self,
        title: Optional[str] = None,
        category: str = "",
        initial_text: str = "",
        content_markdown: Optional[str] = None,
        content_html: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_locked: bool = False,
        sender: Any = None
    ) -> Note:
        """Create a new note."""
        note_id = str(uuid.uuid4())
        clean_cat = (category or "").strip()
        if clean_cat.lower() == "uncategorized":
            clean_cat = ""

        if not title or title.strip() == "" or title.strip() == "Untitled Note":
            title = self.get_next_untitled_title()

        md_content = content_markdown if content_markdown is not None else (initial_text or (f"# {title}\n\n" if not is_untitled_title(title) else ""))
        if content_html is not None:
            html_content = content_html
        else:
            html_content = markdown_to_html(md_content) if md_content else f"<h1>{title}</h1><div><br></div>"
        return self.save_note(
            note_id=note_id,
            title=title,
            category=clean_cat,
            content_html=html_content,
            content_markdown=md_content,
            tags=tags,
            is_locked=is_locked,
            sender=sender
        )

    def delete_note(self, note_id: str, permanent: bool = False, sender: Any = None):
        """Move note to trash, or delete permanently."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if permanent:
                cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
                cursor.execute("DELETE FROM attachments WHERE note_id = ?", (note_id,))
            else:
                cursor.execute("UPDATE notes SET is_trashed = 1, updated_at = ? WHERE id = ?", (time.time(), note_id))
            conn.commit()
        self._notify_change("note-deleted", {"note_id": note_id, "permanent": permanent}, sender=sender)

    def restore_note(self, note_id: str, sender: Any = None):
        """Restore note from trash."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE notes SET is_trashed = 0, updated_at = ? WHERE id = ?", (time.time(), note_id))
            conn.commit()
        self._notify_change("note-restored", {"note_id": note_id}, sender=sender)

    def empty_trash(self, sender: Any = None) -> int:
        """Permanently delete all notes in trash along with their attachments."""
        deleted_count = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM notes WHERE is_trashed = 1")
            rows = cursor.fetchall()
            if rows:
                trashed_ids = [r["id"] for r in rows]
                deleted_count = len(trashed_ids)
                placeholders = ",".join("?" for _ in trashed_ids)
                cursor.execute(f"DELETE FROM attachments WHERE note_id IN ({placeholders})", trashed_ids)
                cursor.execute("DELETE FROM notes WHERE is_trashed = 1")
                conn.commit()
        if deleted_count > 0:
            self._notify_change("trash-emptied", {"count": deleted_count}, sender=sender)
        return deleted_count

    def set_note_pinned(self, note_id: str, is_pinned: bool, sender: Any = None):
        """Set pinned status directly."""
        val = 1 if is_pinned else 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE notes SET is_pinned = ?, updated_at = ? WHERE id = ?", (val, time.time(), note_id))
            conn.commit()
        self._notify_change("note-pin-toggled", {"note_id": note_id, "is_pinned": bool(val)}, sender=sender)

    def set_notes_pinned(self, note_ids: List[str], is_pinned: bool, sender: Any = None):
        """Set pinned status for multiple notes."""
        if not note_ids:
            return
        val = 1 if is_pinned else 0
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in note_ids)
            cursor.execute(f"UPDATE notes SET is_pinned = ?, updated_at = ? WHERE id IN ({placeholders})", [val, now] + note_ids)
            conn.commit()
        for nid in note_ids:
            self._notify_change("note-pin-toggled", {"note_id": nid, "is_pinned": bool(val)}, sender=sender)

    def set_note_category(self, note_id: str, category: str, sender: Any = None):
        """Set category for a single note."""
        clean_cat = (category or "").strip()
        if clean_cat.lower() == "uncategorized":
            clean_cat = ""
        if clean_cat:
            self.create_category(clean_cat)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE notes SET category = ?, updated_at = ? WHERE id = ?", (clean_cat, time.time(), note_id))
            conn.commit()
        self._notify_change("category-changed", {"note_id": note_id, "category": clean_cat}, sender=sender)

    def set_notes_category(self, note_ids: List[str], category: str, sender: Any = None):
        """Set category for multiple notes."""
        if not note_ids:
            return
        clean_cat = (category or "").strip()
        if clean_cat.lower() == "uncategorized":
            clean_cat = ""
        if clean_cat:
            self.create_category(clean_cat)
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in note_ids)
            cursor.execute(f"UPDATE notes SET category = ?, updated_at = ? WHERE id IN ({placeholders})", [clean_cat, now] + note_ids)
            conn.commit()
        self._notify_change("category-changed", {"note_ids": note_ids, "category": clean_cat}, sender=sender)

    def delete_notes(self, note_ids: List[str], permanent: bool = False, sender: Any = None):
        """Move multiple notes to trash, or delete permanently."""
        if not note_ids:
            return
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in note_ids)
            if permanent:
                cursor.execute(f"DELETE FROM notes WHERE id IN ({placeholders})", note_ids)
                cursor.execute(f"DELETE FROM attachments WHERE note_id IN ({placeholders})", note_ids)
            else:
                cursor.execute(f"UPDATE notes SET is_trashed = 1, updated_at = ? WHERE id IN ({placeholders})", [now] + note_ids)
            conn.commit()
        self._notify_change("notes-deleted", {"note_ids": note_ids, "permanent": permanent}, sender=sender)

    def restore_notes(self, note_ids: List[str], sender: Any = None):
        """Restore multiple notes from trash."""
        if not note_ids:
            return
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in note_ids)
            cursor.execute(f"UPDATE notes SET is_trashed = 0, updated_at = ? WHERE id IN ({placeholders})", [now] + note_ids)
            conn.commit()
        self._notify_change("notes-restored", {"note_ids": note_ids}, sender=sender)

    def toggle_pin_note(self, note_id: str, sender: Any = None) -> bool:
        """Toggle pinned status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_pinned FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()
            if row:
                new_state = 0 if row["is_pinned"] else 1
                cursor.execute("UPDATE notes SET is_pinned = ?, updated_at = ? WHERE id = ?", (new_state, time.time(), note_id))
                conn.commit()
                self._notify_change("note-pin-toggled", {"note_id": note_id, "is_pinned": bool(new_state)}, sender=sender)
                return bool(new_state)
        return False

    def toggle_lock_note(self, note_id: str, sender: Any = None) -> bool:
        """Toggle is_locked state for a note."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_locked FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()
            if row:
                curr = bool(row["is_locked"]) if "is_locked" in row.keys() else False
                new_val = 0 if curr else 1
                now = time.time()
                cursor.execute("UPDATE notes SET is_locked = ?, updated_at = ? WHERE id = ?", (new_val, now, note_id))
                conn.commit()
                self._notify_change("note-lock-toggled", {"note_id": note_id, "is_locked": bool(new_val)}, sender=sender)
                return bool(new_val)
        return False

    def set_note_locked(self, note_id: str, is_locked: bool, sender: Any = None):
        """Explicitly set is_locked state for a note."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = time.time()
            cursor.execute("UPDATE notes SET is_locked = ?, updated_at = ? WHERE id = ?", (1 if is_locked else 0, now, note_id))
            conn.commit()
            self._notify_change("note-lock-toggled", {"note_id": note_id, "is_locked": bool(is_locked)}, sender=sender)

    def set_private_password(self, password: str):
        """Set or change the master password for private/locked notes.

        When a master password is set, every locked note's body is re-encrypted
        with a key derived from the new password, so a later password change
        revokes access to all previously locked notes.
        """
        clean = password.strip()
        if not clean:
            return
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            "sha256",
            clean.encode("utf-8"),
            bytes.fromhex(salt),
            100000
        ).hex()
        with self.get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", ("private_note_password_salt", salt))
            conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", ("private_note_password_hash", pwd_hash))
            # Security: never persist the plaintext password to the database.
            # Remove any previously stored plaintext password from older versions.
            conn.execute("DELETE FROM app_settings WHERE key = 'private_note_password'")
            conn.commit()
        # Keep the password in memory only for the current session
        self._session_password = clean
        self._re_encrypt_locked_notes(clean)

    def _re_encrypt_locked_notes(self, password: str):
        """Re-encrypt the bodies of all locked notes under a new master password."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, content_markdown FROM notes WHERE is_locked = 1")
            for note_id, encrypted in cursor.fetchall():
                try:
                    plaintext = self._decrypt_blob(encrypted, password)
                    new_blob = self._encrypt_blob(plaintext, secrets.token_bytes(16), password)
                    cursor.execute(
                        "UPDATE notes SET content_markdown = ?, content_html = ? WHERE id = ?",
                        (new_blob, new_blob, note_id),
                    )
                except Exception:
                    # Non-encrypted / legacy body: leave as-is; it will be encrypted
                    # on the next save of a locked note (or the note will stay
                    # plaintext until a password is set).
                    pass
            conn.commit()

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        """Derive an AES-256 key from the master password and a per-note salt."""
        global HAS_CRYPTOGRAPHY
        if HAS_CRYPTOGRAPHY is None:
            try:
                from cryptography.hazmat.primitives import hashes as _hashes
                from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC as _PBKDF2HMAC
                HAS_CRYPTOGRAPHY = True
            except ImportError:
                HAS_CRYPTOGRAPHY = False
        if not HAS_CRYPTOGRAPHY:
            raise RuntimeError("The 'cryptography' Python module is required for note encryption.")
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.backends import default_backend
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )
        return kdf.derive(password.encode("utf-8"))

    @staticmethod
    def _encrypt_blob(plaintext: str, salt: bytes, password: str) -> str:
        """AES-256-GCM encrypt a note body. Returns base64 'salt||nonce||ct||tag'."""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        key = NoteDatabase._derive_key(password, salt)
        nonce = secrets.token_bytes(12)
        cipher = Cipher(algorithms.AES(key), modes.GCM(nonce), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext.encode("utf-8")) + encryptor.finalize()
        return base64.b64encode(b"".join([salt, nonce, encryptor.tag, ciphertext])).decode("ascii")

    @staticmethod
    def _decrypt_blob(ciphertext_blob: str, password: str) -> str:
        """Decrypt a note body produced by _encrypt_blob."""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        raw = base64.b64decode(ciphertext_blob)
        salt, nonce, tag, ct = raw[:16], raw[16:28], raw[28:44], raw[44:]
        key = NoteDatabase._derive_key(password, salt)
        cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        try:
            pt = decryptor.update(ct) + decryptor.finalize()
        except Exception:
            raise ValueError("Decryption failed: incorrect password or corrupted body")
        return pt.decode("utf-8")

    def has_private_password(self) -> bool:
        """Check if a private notes master password has been configured."""
        return bool(self.get_setting("private_note_password_hash", ""))

    def verify_private_password(self, password: str) -> bool:
        """Verify a plaintext password against the stored salted PBKDF2 hash."""
        salt = self.get_setting("private_note_password_salt", "")
        pwd_hash = self.get_setting("private_note_password_hash", "")
        if not salt or not pwd_hash:
            return False
        computed = hashlib.pbkdf2_hmac(
            "sha256",
            password.strip().encode("utf-8"),
            bytes.fromhex(salt),
            100000
        ).hex()
        if secrets.compare_digest(computed, pwd_hash):
            # Cache the verified password in memory for encryption/decryption
            self._session_password = password.strip()
            return True
        return False

    def _get_session_password(self) -> str:
        """Return the in-memory session password for note encryption/decryption.

        The password is only available after a successful verify_private_password()
        or set_private_password() call during this session. It is never read from
        the database.
        """
        return self._session_password or ""

    def clear_private_password(self):
        """Remove the private notes master password and salt."""
        self._session_password = None
        with self.get_connection() as conn:
            conn.execute("DELETE FROM app_settings WHERE key IN ('private_note_password_salt', 'private_note_password_hash', 'private_note_password')")
            conn.commit()

    def duplicate_note(self, note_id: str) -> Optional[Note]:
        """Duplicate an existing note."""
        note = self.get_note(note_id)
        if not note:
            return None
        new_id = str(uuid.uuid4())
        dup = self.save_note(
            note_id=new_id,
            title=f"{note.title} (Copy)",
            category=note.category,
            content_html=note.content_html,
            content_markdown=note.content_markdown,
            tags=note.tags,
            # A copy of a private note must stay private, otherwise its content
            # would immediately become visible in the public views.
            is_locked=note.is_locked
        )
        # Duplicate attachments
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM attachments WHERE note_id = ?", (note_id,))
            for att in cursor.fetchall():
                self.save_attachment(
                    note_id=new_id,
                    filename=att["filename"],
                    mime_type=att["mime_type"],
                    data=att["data"]
                )
        return dup

    def import_note_from_file(self, file_path: str, sender: Any = None) -> Note:
        """Import a .md or .txt file as a new note, extracting metadata, hashtags, checklists, and updating categories."""
        p = Path(file_path)
        try:
            raw_text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw_text = p.read_text(encoding="latin-1")

        # 1. Parse YAML frontmatter if present
        fm_title = None
        fm_category = None
        fm_tags = []
        body_text = raw_text
        fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', raw_text, re.DOTALL)
        # Only treat the block as frontmatter when it is an actual YAML mapping
        # (key: value). Otherwise a document that starts with a horizontal rule
        # would have its leading text silently swallowed.
        has_yaml_keys = bool(
            fm_match and re.search(r'^\s*[A-Za-z][\w .-]*:\s*\S', fm_match.group(1), re.MULTILINE)
        )
        if fm_match and has_yaml_keys:
            fm_yaml = fm_match.group(1)
            body_text = raw_text[fm_match.end():]
            for line in fm_yaml.splitlines():
                line = line.strip()
                if line.lower().startswith("title:"):
                    fm_title = line.split(":", 1)[1].strip().strip("\"'")
                elif line.lower().startswith("category:"):
                    fm_category = line.split(":", 1)[1].strip().strip("\"'")
                elif line.lower().startswith("tags:"):
                    raw_tags = line.split(":", 1)[1].strip()
                    if raw_tags.startswith("[") and raw_tags.endswith("]"):
                        raw_tags = raw_tags[1:-1]
                    fm_tags = [t.strip().strip("\"'").lstrip("#").lower() for t in raw_tags.split(",") if t.strip()]

        # 2. Extract title
        if fm_title:
            title = fm_title
        else:
            clean_for_title = RE_TAG_EXTRACT.sub('', body_text)
            clean_for_title = RE_CAT_HASH.sub('', clean_for_title)
            extracted_title, _ = extract_title_and_excerpt(clean_for_title)
            if extracted_title and extracted_title != "Untitled Note":
                title = extracted_title
            else:
                title = p.stem.replace("_", " ").strip() or "Untitled Note"

        # Ensure content markdown has title heading if not already present
        clean_body = body_text.strip()
        if not clean_body.startswith("# "):
            content_markdown = f"# {title}\n\n{clean_body}"
        else:
            content_markdown = clean_body

        # 3. Extract hashtags
        extracted_tags = extract_tags(content_markdown)
        all_tags = list(dict.fromkeys(fm_tags + extracted_tags))

        # 4. Check for checklist and list
        has_todo = check_has_todo(content_markdown)

        # 5. Extract / update category
        category = (fm_category or "").strip()
        if not category:
            cat_candidates = extract_categories(content_markdown)
            if cat_candidates:
                category = cat_candidates[0].strip()

        # Check for inline Category: <name> metadata line
        if not category:
            cat_line_match = re.search(r'^(?:Category|Folder):\s*(.+)$', content_markdown, re.MULTILINE | re.IGNORECASE)
            if cat_line_match:
                category = cat_line_match.group(1).strip()

        # Match hashtags against existing categories
        existing_cats = {c.name.lower(): c.name for c in self.get_categories()}
        if not category and all_tags:
            for t in all_tags:
                if t.lower() in existing_cats:
                    category = existing_cats[t.lower()]
                    break

        # If still no category and hashtags exist, use the first hashtag as category
        if not category and all_tags:
            first_tag = all_tags[0]
            category = first_tag.title() if first_tag.islower() else first_tag

        if category and category.lower() == "uncategorized":
            category = ""

        # Ensure category is created in database
        if category:
            self.create_category(category)

        # 6. Create note in database
        note = self.create_note(
            title=title,
            category=category,
            initial_text=content_markdown,
            tags=all_tags,
            sender=sender
        )
        return note

    # ── Attachments API ───────────────────────────────────────────────────

    def save_attachment(
        self,
        note_id: str,
        filename: str,
        mime_type: str,
        data: bytes,
        attachment_id: Optional[str] = None
    ) -> str:
        """Store image or file as a binary blob in the attachments table."""
        att_id = attachment_id or str(uuid.uuid4())
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO attachments (id, note_id, filename, mime_type, data, size_bytes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (att_id, note_id, filename, mime_type, data, len(data), now))
            conn.commit()
        return att_id

    def get_attachment(self, attachment_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve attachment binary data and metadata."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "note_id": row["note_id"],
                    "filename": row["filename"],
                    "mime_type": row["mime_type"],
                    "data": row["data"],
                    "size_bytes": row["size_bytes"],
                }
            return None

    def delete_attachment(self, attachment_id: str):
        """Delete specific attachment."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
            conn.commit()

    def _resolve_attachment_uri_to_bytes(self, cursor, url: str) -> Optional[bytes]:
        """Resolve an image URI to binary data within an existing DB cursor."""
        if not url:
            return None
        if url.startswith("attachment://") or url.startswith("attachment:"):
            prefix = "attachment://" if url.startswith("attachment://") else "attachment:"
            att_id = url[len(prefix):].split("/")[0].split("?")[0].split("#")[0]
            cursor.execute("SELECT data FROM attachments WHERE id = ? AND data IS NOT NULL", (att_id,))
            r = cursor.fetchone()
            if r and r["data"]:
                return r["data"]
            if "." in att_id:
                base_id = att_id.rsplit(".", 1)[0]
                cursor.execute("SELECT data FROM attachments WHERE id = ? AND data IS NOT NULL", (base_id,))
                r = cursor.fetchone()
                if r and r["data"]:
                    return r["data"]
        elif url.startswith("data:image/") and ";base64," in url:
            try:
                b64_part = url.split(";base64,", 1)[1]
                return base64.b64decode(b64_part)
            except Exception:
                pass
        elif url.startswith("file://") or (url.startswith("/") and os.path.isabs(url)):
            local_path = url[len("file://"):] if url.startswith("file://") else url
            local_path = urllib.parse.unquote(local_path)
            # Security: only allow reading files from known safe directories
            safe_prefixes = (
                str(Path(GLib.get_user_data_dir())),
                str(Path(GLib.get_user_cache_dir())),
                "/tmp/",
            )
            resolved = str(Path(local_path).resolve())
            if os.path.isfile(local_path) and any(resolved.startswith(p) for p in safe_prefixes):
                try:
                    with open(local_path, "rb") as f:
                        return f.read()
                except Exception:
                    pass
        return None

    def get_note_first_image(self, note_id: str) -> Optional[bytes]:
        """Retrieve binary data for the top-most primary image of a note.
        
        If a note has multiple images, only the top-most (first in document order)
        image is returned; subsequent images are ignored.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 1. First check the note's content to find the top-most image in document order
            cursor.execute("SELECT content_markdown, content_html FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()
            if row:
                content = row["content_markdown"] or row["content_html"] or ""
                if content:
                    matches = []
                    for m in re.finditer(r'!\[.*?\]\((.+?)\)', content):
                        raw_url = m.group(1).strip().split()[0]
                        if raw_url:
                            matches.append((m.start(), raw_url))
                    for m in re.finditer(r'<img\s+[^>]*?src=["\']([^"\']+)["\']', content, re.IGNORECASE):
                        raw_url = m.group(1).strip()
                        if raw_url:
                            matches.append((m.start(), raw_url))

                    matches.sort(key=lambda x: x[0])
                    for _, url in matches:
                        data = self._resolve_attachment_uri_to_bytes(cursor, url)
                        if data:
                            return data

            return None

    def get_note_first_table(self, note_id: str) -> Optional[List[List[str]]]:
        """Retrieve structured table rows for the first table of a note if present."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content_markdown, content_html FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()
            if row:
                content = row["content_markdown"] or row["content_html"] or ""
                if content and ("|" in content or "<table" in content.lower()):
                    return extract_table_data(content)
        return None

    def get_categories(self) -> List[Category]:
        """Fetch categories with active note counts in that category and its subcategories."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, icon, color, sort_order FROM categories WHERE LOWER(name) != 'uncategorized' ORDER BY sort_order ASC, name ASC")
            cat_rows = cursor.fetchall()

            # Note counts per category including subcategories (without counting subcategories as notes)
            cursor.execute(
                "SELECT category, COUNT(*) as cnt FROM notes "
                "WHERE is_trashed = 0 AND is_locked = 0 AND category != '' AND category IS NOT NULL AND LOWER(category) != 'uncategorized' "
                "GROUP BY category"
            )
            note_rows = cursor.fetchall()
            cat_counts: Dict[str, int] = {}
            for row in note_rows:
                cat = row["category"]
                cnt = row["cnt"]
                parts = cat.split("/")
                for i in range(len(parts)):
                    ancestor = "/".join(parts[:i + 1])
                    cat_counts[ancestor] = cat_counts.get(ancestor, 0) + cnt

            return [
                Category(
                    id=row["id"],
                    name=row["name"],
                    icon=row["icon"] or "folder-symbolic",
                    color=row["color"] or "",
                    count=cat_counts.get(row["name"], 0),
                    sort_order=row["sort_order"] if "sort_order" in row.keys() else 0,
                )
                for row in cat_rows
            ]

    def create_category(self, name: str, icon: str = "folder-symbolic", color: str = "", sender: Any = None) -> bool:
        """Create a new category."""
        clean_name = name.strip()
        if not clean_name or clean_name.lower() == "uncategorized":
            return False
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order FROM categories")
                next_order = cursor.fetchone()["next_order"]
                cursor.execute(
                    "INSERT INTO categories (id, name, icon, color, sort_order, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), clean_name, icon, color, next_order, time.time())
                )
                conn.commit()
            self._notify_change("categories-updated", {"category": clean_name}, sender=sender)
            return True
        except sqlite3.IntegrityError:
            return False

    def reorder_categories(self, ordered_names: List[str], sender: Any = None):
        """Update the sort_order of categories to match the provided list order."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for idx, name in enumerate(ordered_names):
                cursor.execute("UPDATE categories SET sort_order = ? WHERE name = ?", (idx, name))
            conn.commit()
        self._notify_change("categories-updated", {"reordered": ordered_names}, sender=sender)

    def rename_category(self, old_name: str, new_name: str, sender: Any = None):
        """Rename a category and all its subcategories and update affected notes."""
        old_name = old_name.strip()
        new_name = new_name.strip()
        if not old_name or not new_name or old_name == new_name:
            return
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM categories WHERE name = ?", (new_name,))
            if cursor.fetchone():
                cursor.execute("DELETE FROM categories WHERE name = ?", (old_name,))
            else:
                cursor.execute("UPDATE categories SET name = ? WHERE name = ?", (new_name, old_name))
            old_prefix = old_name + "/"
            new_prefix = new_name + "/"
            cursor.execute(
                "UPDATE categories SET name = ? || substr(name, ?) WHERE name LIKE ?",
                (new_prefix, len(old_prefix) + 1, old_prefix + "%")
            )
            cursor.execute("UPDATE notes SET category = ?, updated_at = ? WHERE category = ?", (new_name, now, old_name))
            cursor.execute(
                "UPDATE notes SET category = ? || substr(category, ?), updated_at = ? WHERE category LIKE ?",
                (new_prefix, len(old_prefix) + 1, now, old_prefix + "%")
            )
            conn.commit()
        self._notify_change("categories-updated", {"old_name": old_name, "new_name": new_name}, sender=sender)

    def delete_category(self, name: str, sender: Any = None):
        """Delete category and any subcategories and reset affected notes' category."""
        clean_name = name.strip()
        if not clean_name:
            return
        now = time.time()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM categories WHERE name = ? OR name LIKE ?", (clean_name, clean_name + "/%"))
            cursor.execute(
                "UPDATE notes SET category = '', updated_at = ? WHERE category = ? OR category LIKE ?",
                (now, clean_name, clean_name + "/%")
            )
            conn.commit()
        self._notify_change("categories-updated", {"deleted": clean_name}, sender=sender)

    def get_counts(self) -> Dict[str, int]:
        """Return counts for standard tabs plus per-category counts in 2 fast queries."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT
                COUNT(CASE WHEN is_trashed = 0 AND is_locked = 0 THEN 1 END) as all_cnt,
                COUNT(CASE WHEN is_trashed = 0 AND is_locked = 0 AND is_pinned = 1 THEN 1 END) as pinned_cnt,
                COUNT(CASE WHEN is_trashed = 0 AND is_locked = 0 AND has_todo = 1 THEN 1 END) as todo_cnt,
                COUNT(CASE WHEN is_trashed = 0 AND is_locked = 0 AND has_list = 1 THEN 1 END) as list_cnt,
                COUNT(CASE WHEN is_trashed = 0 AND is_locked = 0 AND has_link = 1 THEN 1 END) as link_cnt,
                COUNT(CASE WHEN is_trashed = 0 AND is_locked = 1 THEN 1 END) as private_cnt,
                COUNT(CASE WHEN is_trashed = 0 AND is_locked = 0 AND (category = '' OR category IS NULL) THEN 1 END) as uncat_cnt,
                COUNT(CASE WHEN is_trashed = 1 THEN 1 END) as trash_cnt
            FROM notes
            """)
            counts_row = cursor.fetchone()
            all_cnt = counts_row["all_cnt"]
            pinned_cnt = counts_row["pinned_cnt"]
            todo_cnt = counts_row["todo_cnt"]
            list_cnt = counts_row["list_cnt"]
            link_cnt = counts_row["link_cnt"]
            private_cnt = counts_row["private_cnt"]
            uncat_cnt = counts_row["uncat_cnt"]
            trash_cnt = counts_row["trash_cnt"]

            cursor.execute(
                "SELECT category, COUNT(*) as cnt FROM notes "
                "WHERE is_trashed = 0 AND is_locked = 0 AND category != '' AND category IS NOT NULL "
                "GROUP BY category"
            )
            cat_rows = cursor.fetchall()
            cat_counts: Dict[str, int] = {}
            for row in cat_rows:
                cat = row["category"]
                cnt = row["cnt"]
                parts = cat.split("/")
                for i in range(len(parts)):
                    ancestor = "/".join(parts[:i + 1])
                    cat_counts[f"cat:{ancestor}"] = cat_counts.get(f"cat:{ancestor}", 0) + cnt

            result = {
                "all": all_cnt,
                "pinned": pinned_cnt,
                "favorites": pinned_cnt,
                "todo": todo_cnt,
                "todos": todo_cnt,
                "list": list_cnt,
                "lists": list_cnt,
                "linked": link_cnt,
                "links": link_cnt,
                "private": private_cnt,
                "locked": private_cnt,
                "recent": all_cnt,
                "uncategorized": uncat_cnt,
                "trash": trash_cnt,
            }
            result.update(cat_counts)
            for tag_name, cnt in self.get_all_tags():
                result[f"tag:{tag_name}"] = cnt
            return result

    def _create_category_sync(self, conn: sqlite3.Connection, full_name: str):
        """Helper to create category and missing ancestor categories within an existing transaction."""
        clean = (full_name or "").strip()
        if not clean or clean.lower() == "uncategorized":
            return
        parts = clean.split("/")
        now = time.time()
        for i in range(len(parts)):
            sub = "/".join(parts[:i + 1]).strip()
            if not sub or sub.lower() == "uncategorized":
                continue
            conn.execute(
                "INSERT OR IGNORE INTO categories (id, name, created_at) VALUES (?, ?, ?)",
                (str(uuid.uuid4()), sub, now)
            )

    def get_all_tags(self, include_locked: bool = False) -> List[Tuple[str, int]]:
        """Return list of (tag_name, count) for all tags in non-trashed notes, sorted by count."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cond = "" if include_locked else " AND is_locked = 0"
            # Fast path: query only the tags column without loading large content fields
            cursor.execute(f"SELECT tags FROM notes WHERE is_trashed = 0{cond} AND tags IS NOT NULL AND tags != '' AND tags != '[]'")
            tag_counts: Dict[str, int] = {}
            for r in cursor.fetchall():
                raw = r["tags"]
                if not raw:
                    continue
                try:
                    t_list = json.loads(raw)
                except Exception:
                    t_list = [x.strip() for x in str(raw).split(",") if x.strip()]
                note_tags = set()
                for t in t_list:
                    t_clean = t.strip().lstrip("#").lower().replace("\\ ", " ")
                    # Older editor builds could include punctuation and a second
                    # hashtag in one saved name (for example ".#love"). Keep the
                    # actual hashtag name and count it only once per note.
                    if "#" in t_clean:
                        t_clean = t_clean.rsplit("#", 1)[-1]
                    if t_clean:
                        note_tags.add(t_clean)
                for t_clean in note_tags:
                    tag_counts[t_clean] = tag_counts.get(t_clean, 0) + 1

            # Fallback only for unmigrated notes that have hashtags but no tags column value
            cursor.execute(f"SELECT content_markdown FROM notes WHERE is_trashed = 0{cond} AND (tags IS NULL OR tags = '' OR tags = '[]') AND content_markdown LIKE '%#%'")
            for r in cursor.fetchall():
                if r["content_markdown"]:
                    for t in extract_tags(r["content_markdown"]):
                        t_clean = t.strip().lstrip("#").lower()
                        if t_clean:
                            tag_counts[t_clean] = tag_counts.get(t_clean, 0) + 1

            return sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))

    def delete_tag(self, tag_name: str):
        """Remove a tag from all notes."""
        clean = tag_name.strip().lstrip("#").lower()
        if not clean:
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, tags FROM notes WHERE is_trashed = 0")
            for r in cursor.fetchall():
                note_id = r["id"]
                raw = r["tags"]
                if not raw:
                    continue
                try:
                    t_list = json.loads(raw)
                    if isinstance(t_list, list):
                        new_list = [t for t in t_list if t.strip().lstrip("#").lower() != clean]
                        if len(new_list) != len(t_list):
                            cursor.execute("UPDATE notes SET tags = ? WHERE id = ?", (json.dumps(new_list), note_id))
                except Exception:
                    pass
            conn.commit()
        self._notify_change("tag-deleted", {"tag": clean})

    def rename_tag(self, old_tag: str, new_tag: str):
        """Rename a tag across all notes."""
        old_clean = old_tag.strip().lstrip("#").lower()
        new_clean = new_tag.strip().lstrip("#").lower()
        if not old_clean or not new_clean or old_clean == new_clean:
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, tags FROM notes WHERE is_trashed = 0")
            for r in cursor.fetchall():
                note_id = r["id"]
                raw = r["tags"]
                if not raw:
                    continue
                try:
                    t_list = json.loads(raw)
                    if isinstance(t_list, list):
                        modified = False
                        new_list = []
                        for t in t_list:
                            if t.strip().lstrip("#").lower() == old_clean:
                                if new_clean not in new_list:
                                    new_list.append(new_clean)
                                modified = True
                            else:
                                if t not in new_list:
                                    new_list.append(t)
                        if modified:
                            cursor.execute("UPDATE notes SET tags = ? WHERE id = ?", (json.dumps(new_list), note_id))
                except Exception:
                    pass
            conn.commit()
        self._notify_change("tag-renamed", {"old_tag": old_clean, "new_tag": new_clean})

    def find_note_by_title(self, title: str) -> Optional[Note]:
        """Find non-trashed note by title (case-insensitive exact match)."""
        clean_title = title.strip()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM notes WHERE is_trashed = 0 AND LOWER(TRIM(title)) = LOWER(?) LIMIT 1",
                (clean_title,)
            )
            row = cursor.fetchone()
            if row:
                return Note.from_row(row)
            return None

    def get_all_note_titles(self, include_locked: bool = False) -> List[str]:
        """Return list of distinct note titles for internal link autocompletion.

        Locked private note titles are excluded by default so that they never
        leak into the editor's wiki-link suggestions.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = (
                "SELECT DISTINCT title FROM notes WHERE is_trashed = 0 "
                "AND title IS NOT NULL AND title != '' AND title NOT LIKE 'Untitled Note%'"
            )
            if not include_locked:
                query += " AND is_locked = 0"
            cursor.execute(query)
            return [r["title"] for r in cursor.fetchall()]

    def get_setting(self, key: str, default: str = "") -> str:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                return row["value"] if row else default
        except Exception:
            return default

    def set_setting(self, key: str, value: str):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, str(value)))
                conn.commit()
        except Exception as e:
            print("Error saving setting:", e)

    def backup_to_file(self, target_path: str, exclude_private: bool = False):
        """Export a clean, atomic snapshot of this SQLite database to target_path."""
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self.get_connection() as src_conn:
            # Checkpoint WAL if not in-memory
            if str(self.db_path) != ":memory:":
                try:
                    src_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                except Exception:
                    pass
            dest_conn = sqlite3.connect(str(target))
            try:
                src_conn.backup(dest_conn)
                if exclude_private:
                    cur = dest_conn.cursor()
                    cur.execute("SELECT id FROM notes WHERE is_locked = 1")
                    locked_ids = [row[0] for row in cur.fetchall()]
                    if locked_ids:
                        placeholders = ",".join("?" * len(locked_ids))
                        cur.execute(f"DELETE FROM attachments WHERE note_id IN ({placeholders})", locked_ids)
                        cur.execute("DELETE FROM notes WHERE is_locked = 1")
                    cur.execute("DELETE FROM app_settings WHERE key IN ('private_note_password_salt', 'private_note_password_hash', 'private_note_password', 'auto_backup_password')")
                    dest_conn.commit()
                    dest_conn.execute("VACUUM")
            finally:
                dest_conn.close()

    def restore_from_file(self, source_path: str, sender: Any = None):
        """Restore database state from a backup file and notify change listeners."""
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Backup file not found: {source_path}")

        src_conn = sqlite3.connect(str(source))
        try:
            with self.get_connection() as dest_conn:
                src_conn.backup(dest_conn)
                dest_conn.commit()
                if str(self.db_path) != ":memory:":
                    try:
                        dest_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    except Exception:
                        pass
        finally:
            src_conn.close()

        self._notify_change("database-restored", {}, sender=sender)
