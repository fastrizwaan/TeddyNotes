# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import base64
from collections import OrderedDict
import os
import re
import urllib.parse
from datetime import datetime, timedelta
from typing import List, Optional
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Adw, Gtk, Gdk, Gio, GLib, GObject, Pango, GdkPixbuf

from teddynotes.models import Note
from teddynotes.markdown_utils import strip_markdown, extract_table_data


_TEXTURE_CACHE: dict = {}
_IMAGE_BYTES_CACHE = OrderedDict()
_IMAGE_BYTES_CACHE_MAX_ENTRIES = 256
_IMAGE_BYTES_CACHE_MAX_BYTES = 8 * 1024 * 1024
_IMAGE_BYTES_CACHE_SIZE = 0


def _resolve_image_bytes(url: str, db=None) -> Optional[bytes]:
    """Resolve an image URL (attachment://, data:image, file://) to raw bytes."""
    if not url:
        return None

    if url.startswith("attachment://") or url.startswith("attachment:"):
        prefix = "attachment://" if url.startswith("attachment://") else "attachment:"
        att_id = url[len(prefix):].split("/")[0].split("?")[0].split("#")[0]
        if db and hasattr(db, "get_attachment"):
            try:
                att = db.get_attachment(att_id)
                if att and att.get("data"):
                    return att["data"]
                if "." in att_id:
                    att = db.get_attachment(att_id.rsplit(".", 1)[0])
                    if att and att.get("data"):
                        return att["data"]
            except Exception:
                pass

    elif url.startswith("data:image/") and ";base64," in url:
        try:
            b64_part = url.split(";base64,", 1)[1]
            return base64.b64decode(b64_part)
        except Exception:
            pass

    elif url.startswith("file://") or (url.startswith("/") and os.path.isabs(url)):
        local_path = url[len("file://"):] if url.startswith("file://") else url
        local_path = urllib.parse.unquote(local_path)
        if os.path.isfile(local_path):
            try:
                with open(local_path, "rb") as f:
                    return f.read()
            except Exception:
                pass

    return None


def get_note_image_bytes(note: Note, db=None) -> Optional[bytes]:
    """Retrieve raw image bytes for preview if note has an image.

    If a note has multiple images, only the top-most Primary Image is returned.
    Subsequent images are ignored in card preview.
    """
    # 1. Check in-memory content on the note object if present
    content = ""
    if note.content_markdown:
        content = note.content_markdown
    elif note.content_html:
        content = note.content_html

    if content:
        # Collect all images in document order (top to bottom)
        matches = []
        for m in re.finditer(r'!\[.*?\]\((.+?)\)', content):
            raw_url = m.group(1).strip().split()[0]
            if raw_url:
                matches.append((m.start(), raw_url))
        for m in re.finditer(r'<img\s+[^>]*?src=["\']([^"\']+)["\']', content, re.IGNORECASE):
            raw_url = m.group(1).strip()
            if raw_url:
                matches.append((m.start(), raw_url))

        if matches:
            matches.sort(key=lambda x: x[0])
            for _, url in matches:
                data = _resolve_image_bytes(url, db)
                if data:
                    return data
        return None

    # 2. If content was not on the note object (e.g. lightweight Note), use fast DB method
    if db and hasattr(db, "get_note_first_image"):
        cache_key = (note.id, note.updated_at)
        cached = _IMAGE_BYTES_CACHE.get(cache_key, ...)
        if cached is not ...:
            _IMAGE_BYTES_CACHE.move_to_end(cache_key)
            return cached

        image_bytes = None
        try:
            image_bytes = db.get_note_first_image(note.id)
        except Exception:
            pass

        # Cache repeated body lookups across list rebuilds, with a strict memory bound.
        global _IMAGE_BYTES_CACHE_SIZE
        if image_bytes is None or len(image_bytes) <= _IMAGE_BYTES_CACHE_MAX_BYTES:
            _IMAGE_BYTES_CACHE[cache_key] = image_bytes
            if image_bytes:
                _IMAGE_BYTES_CACHE_SIZE += len(image_bytes)
            while (
                len(_IMAGE_BYTES_CACHE) > _IMAGE_BYTES_CACHE_MAX_ENTRIES
                or _IMAGE_BYTES_CACHE_SIZE > _IMAGE_BYTES_CACHE_MAX_BYTES
            ):
                _, evicted = _IMAGE_BYTES_CACHE.popitem(last=False)
                if evicted:
                    _IMAGE_BYTES_CACHE_SIZE -= len(evicted)
        return image_bytes
    elif db and hasattr(db, "get_note"):
        db_note = db.get_note(note.id)
        if db_note:
            return get_note_image_bytes(db_note, db)

    return None


def _create_thumbnail_texture(img_bytes: bytes) -> Optional[Gdk.Texture]:
    """Create a bounded Gdk.Texture from image bytes, scaled and center-cropped to 216x80."""
    cache_key = (len(img_bytes), hash(img_bytes[:128]), hash(img_bytes[-128:]))
    if cache_key in _TEXTURE_CACHE:
        return _TEXTURE_CACHE[cache_key]

    loader = None
    try:
        loader = GdkPixbuf.PixbufLoader()
        loader.write(img_bytes)
        loader.close()
        pix = loader.get_pixbuf()
        loader = None
        if pix:
            target_w, target_h = 216, 80
            w, h = pix.get_width(), pix.get_height()
            if w > 0 and h > 0:
                scale = max(target_w / w, target_h / h)
                scaled_w = max(target_w, int(w * scale))
                scaled_h = max(target_h, int(h * scale))
                pix_scaled = pix.scale_simple(scaled_w, scaled_h, GdkPixbuf.InterpType.BILINEAR)
                if pix_scaled:
                    src_x = max(0, (scaled_w - target_w) // 2)
                    src_y = max(0, (scaled_h - target_h) // 2)
                    pix_cropped = GdkPixbuf.Pixbuf.new(
                        GdkPixbuf.Colorspace.RGB,
                        pix.get_has_alpha(),
                        8,
                        target_w,
                        target_h
                    )
                    pix_scaled.copy_area(src_x, src_y, target_w, target_h, pix_cropped, 0, 0)
                    success, buf = pix_cropped.save_to_bufferv("png", [], [])
                    if success:
                        tex = Gdk.Texture.new_from_bytes(GLib.Bytes.new(buf))
                        if len(_TEXTURE_CACHE) > 200:
                            keys_to_remove = list(_TEXTURE_CACHE.keys())[:50]
                            for k in keys_to_remove:
                                _TEXTURE_CACHE.pop(k, None)
                        _TEXTURE_CACHE[cache_key] = tex
                        return tex
    except Exception:
        pass
    finally:
        if loader is not None:
            try:
                loader.close()
            except Exception:
                pass
    return None


_TABLE_CACHE: dict = {}


def get_note_table_data(note: Note, db=None) -> Optional[List[List[str]]]:
    """Retrieve structured table rows for preview if note has a table."""
    cache_key = (note.id, note.updated_at)
    if cache_key in _TABLE_CACHE:
        return _TABLE_CACHE[cache_key]

    # 1. Check in-memory content
    content = ""
    if note.content_markdown:
        content = note.content_markdown
    elif note.content_html:
        content = note.content_html

    if content and ("|" in content or "<table" in content.lower()):
        data = extract_table_data(content)
        if data:
            if len(_TABLE_CACHE) > 200:
                for k in list(_TABLE_CACHE.keys())[:50]:
                    _TABLE_CACHE.pop(k, None)
            _TABLE_CACHE[cache_key] = data
            return data

    # 2. Check database
    if db and hasattr(db, "get_note_first_table"):
        try:
            data = db.get_note_first_table(note.id)
            if len(_TABLE_CACHE) > 200:
                for k in list(_TABLE_CACHE.keys())[:50]:
                    _TABLE_CACHE.pop(k, None)
            _TABLE_CACHE[cache_key] = data
            return data
        except Exception:
            pass

    _TABLE_CACHE[cache_key] = None
    return None


def _create_table_preview_widget(table_rows: List[List[str]]) -> Optional[Gtk.Widget]:
    """Create a partial table preview widget (216x80) matching the image banner dimensions."""
    if not table_rows or not table_rows[0]:
        return None

    outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    outer_box.set_size_request(-1, 80)
    outer_box.set_hexpand(True)
    outer_box.set_vexpand(False)
    outer_box.set_halign(Gtk.Align.FILL)
    outer_box.set_valign(Gtk.Align.FILL)
    outer_box.set_overflow(Gtk.Overflow.HIDDEN)
    outer_box.add_css_class("note-grid-table-preview")

    grid = Gtk.Grid()
    grid.set_column_homogeneous(True)
    grid.set_hexpand(True)
    grid.set_vexpand(False)
    grid.set_row_spacing(0)
    grid.set_column_spacing(0)

    # Show up to 4 columns and up to 3 rows (header + 2 rows) within the 80px banner
    num_cols = min(len(table_rows[0]), 4)
    display_rows = table_rows[:3]

    for r_idx, row in enumerate(display_rows):
        is_header = (r_idx == 0)
        for c_idx in range(num_cols):
            cell_text = row[c_idx] if c_idx < len(row) else ""
            lbl = Gtk.Label(label=cell_text)
            lbl.set_halign(Gtk.Align.START)
            lbl.set_xalign(0.0)
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            lbl.set_lines(1)
            lbl.set_single_line_mode(True)
            lbl.set_max_width_chars(8)
            lbl.set_hexpand(True)

            cell_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            cell_box.set_hexpand(True)
            cell_box.append(lbl)

            if is_header:
                cell_box.add_css_class("note-grid-table-header")
            else:
                cell_box.add_css_class("note-grid-table-cell")

            if c_idx < num_cols - 1:
                cell_box.add_css_class("table-col-sep")

            grid.attach(cell_box, c_idx, r_idx, 1, 1)

    outer_box.append(grid)
    return outer_box


def _get_note_preview(note: Note) -> str:
    """Extract a short preview while retaining checklist and list markers."""
    text = note.preview_content or note.content_markdown or note.content_html or note.excerpt or ""
    if not text:
        return "Type text here..."

    # Convert stored editor HTML list blocks to simple Markdown-like lines.
    def _html_task(match):
        block = match.group(0)
        checked = bool(re.search(r"<input[^>]*\bchecked(?:=[\"\'][^\"\']*[\"\'])?", block, re.IGNORECASE))
        content = re.sub(r"<input\b[^>]*>", "", match.group(1), flags=re.IGNORECASE)
        return f"- [{'x' if checked else ' '}] {content}\n"

    text = re.sub(
        r"<div[^>]*class=[\"\'][^\"\']*stilo-task[^\"\']*[\"\'][^>]*>(.*?)</div>",
        _html_task, text, flags=re.DOTALL | re.IGNORECASE
    )
    def _html_ordered_list(match):
        items = re.findall(r"<li\b[^>]*>(.*?)</li>", match.group(1), flags=re.DOTALL | re.IGNORECASE)
        return "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1))
    text = re.sub(r"<ol\b[^>]*>(.*?)</ol>", _html_ordered_list, text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<li\b[^>]*>(.*?)</li>", r"- \1\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"</?ul\b[^>]*>", "\n", text, flags=re.IGNORECASE)

    # Remove images and tables before splitting so their markup cannot leak into text.
    text = re.sub(r'!\[.*?\]\([^)]+\)', "", text)
    text = re.sub(r'<div[^>]*class=["\'][^"\']*stilo-img-wrapper[^"\'][^>]*>.*?</div>', "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<img[^>]*>', "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<table[^>]*>.*?</table>', "", text, flags=re.DOTALL | re.IGNORECASE)

    lines = text.splitlines()
    if lines and strip_markdown(lines[0]).strip() == (note.title or "").strip():
        lines = lines[1:]

    preview_lines = []
    task_re = re.compile(r"^\s*[-*+]\s+\[([ xX])\]\s*(.*)$")
    ordered_re = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")
    bullet_re = re.compile(r"^\s*[-*+]\s+(.*)$")
    for line in lines:
        stripped = line.strip()
        if not stripped or (stripped.startswith("|") and stripped.endswith("|")):
            continue
        task = task_re.match(stripped)
        ordered = ordered_re.match(stripped)
        bullet = bullet_re.match(stripped)
        if task:
            marker = "☑" if task.group(1).lower() == "x" else "☐"
            content = strip_markdown(task.group(2)).strip()
            rendered = f"{marker} {content}"
        elif ordered:
            content = strip_markdown(ordered.group(2)).strip()
            rendered = f"{ordered.group(1)}. {content}"
        elif bullet:
            content = strip_markdown(bullet.group(1)).strip()
            rendered = f"• {content}"
        else:
            rendered = strip_markdown(stripped).strip()
        if rendered:
            preview_lines.append(rendered)

    clean = "  ·  ".join(preview_lines[:8]).strip()
    return clean if clean else "Type text here..."


class BaseNoteCard(Gtk.FlowBoxChild):
    __gtype_name__ = "BaseNoteCard"

    __gsignals__ = {
        "pin-toggled": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "copy-link": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "duplicate": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "delete": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "restore": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "perm-delete": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "toggled": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
    }

    def __init__(self, note: Note, db=None, selection_mode: bool = False, show_category_pill: bool = True, is_private_locked: bool = False):
        super().__init__()
        self.note = note
        self.db = db
        self.show_category_pill = show_category_pill
        self.is_private_locked = is_private_locked
        self.card_box: Optional[Gtk.Box] = None
        self.revealer: Optional[Gtk.Revealer] = None
        self.checkbox: Optional[Gtk.CheckButton] = None

        self._build_ui(selection_mode)
        self._setup_context_menu()

    def _build_ui(self, selection_mode: bool):
        raise NotImplementedError

    def _setup_context_menu(self):
        gesture = Gtk.GestureClick.new()
        gesture.set_button(3)  # Secondary / Right click

        def on_pressed(_g, _n, _x, _y):
            menu = Gio.Menu()
            pin_label = "Unpin Note" if self.note.is_pinned else "Pin to Top"
            menu.append(pin_label, f"row.pin::{self.note.id}")
            menu.append("Duplicate", f"row.duplicate::{self.note.id}")

            
            if not self.note.is_trashed:
                menu.append("Copy Link to Note", f"row.copy_link::{self.note.id}")

            if self.note.is_trashed:
                menu.append("Restore Note", f"row.restore::{self.note.id}")
                menu.append("Delete Permanently", f"row.perm_delete::{self.note.id}")
            else:
                menu.append("Move to Trash", f"row.trash::{self.note.id}")

            popover = Gtk.PopoverMenu.new_from_model(menu)
            popover.set_parent(self)
            popover.set_has_arrow(False)

            action_group = Gio.SimpleActionGroup.new()

            act_pin = Gio.SimpleAction.new("pin", GLib.VariantType.new("s"))
            act_pin.connect("activate", lambda _a, p: self.emit("pin-toggled", p.get_string()))
            action_group.add_action(act_pin)

            act_dup = Gio.SimpleAction.new("duplicate", GLib.VariantType.new("s"))
            act_dup.connect("activate", lambda _a, p: self.emit("duplicate", p.get_string()))
            action_group.add_action(act_dup)

            act_trash = Gio.SimpleAction.new("trash", GLib.VariantType.new("s"))
            act_trash.connect("activate", lambda _a, p: self.emit("delete", p.get_string()))
            action_group.add_action(act_trash)
            act_copy = Gio.SimpleAction.new("copy_link", GLib.VariantType.new("s"))
            act_copy.connect("activate", lambda _a, p: self.emit("copy-link", p.get_string()))
            action_group.add_action(act_copy)


            act_res = Gio.SimpleAction.new("restore", GLib.VariantType.new("s"))
            act_res.connect("activate", lambda _a, p: self.emit("restore", p.get_string()))
            action_group.add_action(act_res)

            act_perm = Gio.SimpleAction.new("perm_delete", GLib.VariantType.new("s"))
            act_perm.connect("activate", lambda _a, p: self.emit("perm-delete", p.get_string()))
            action_group.add_action(act_perm)

            self.insert_action_group("row", action_group)
            popover.popup()

        gesture.connect("pressed", on_pressed)
        self.add_controller(gesture)

    def set_selection_mode(self, enabled: bool):
        if self.revealer:
            self.revealer.set_reveal_child(enabled)

    def is_checked(self) -> bool:
        return self.checkbox.get_active() if self.checkbox else False

    def set_checked(self, checked: bool):
        if self.checkbox:
            self.checkbox.set_active(checked)
        if self.card_box:
            if checked:
                self.card_box.add_css_class("checked")
            else:
                self.card_box.remove_css_class("checked")


class NoteGridCard(BaseNoteCard):
    __gtype_name__ = "NoteGridCard"

    def _build_ui(self, selection_mode: bool):
        self.set_size_request(200, 140)
        self.set_hexpand(True)
        self.set_halign(Gtk.Align.FILL)
        self.set_overflow(Gtk.Overflow.HIDDEN)

        self.card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.card_box.add_css_class("note-grid-card")
        self.card_box.set_hexpand(True)
        self.card_box.set_vexpand(True)
        self.card_box.set_overflow(Gtk.Overflow.HIDDEN)

        if self.is_private_locked:
            self.card_box.add_css_class("locked-note-card")
            top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            top_box.set_hexpand(True)

            self.revealer = Gtk.Revealer()
            self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT)
            self.revealer.set_reveal_child(selection_mode)

            self.checkbox = Gtk.CheckButton()
            self.checkbox.set_valign(Gtk.Align.CENTER)
            self.checkbox.connect("toggled", self._on_checkbox_toggled)
            self.revealer.set_child(self.checkbox)
            top_box.append(self.revealer)

            lock_icon = Gtk.Image.new_from_icon_name("channel-secure-symbolic")
            lock_icon.add_css_class("dimmed")
            lock_icon.set_pixel_size(16)
            top_box.append(lock_icon)

            self.title_lbl = Gtk.Label(label="Locked Note")
            self.title_lbl.add_css_class("note-grid-title")
            self.title_lbl.set_halign(Gtk.Align.FILL)
            self.title_lbl.set_hexpand(True)
            self.title_lbl.set_xalign(0.0)
            top_box.append(self.title_lbl)
            self.card_box.append(top_box)

            try:
                dt = datetime.fromtimestamp(self.note.updated_at)
                date_str = dt.strftime("%A, %d/%m %H:%M")
            except Exception:
                date_str = ""
            if date_str:
                self.date_lbl = Gtk.Label(label=date_str)
                self.date_lbl.add_css_class("note-grid-date")
                self.date_lbl.set_halign(Gtk.Align.FILL)
                self.date_lbl.set_hexpand(True)
                self.date_lbl.set_xalign(0.0)
                self.date_lbl.set_lines(1)
                self.card_box.append(self.date_lbl)

            center_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            center_box.set_valign(Gtk.Align.CENTER)
            center_box.set_halign(Gtk.Align.CENTER)
            center_box.set_vexpand(True)
            center_lock = Gtk.Image.new_from_icon_name("channel-secure-symbolic")
            center_lock.set_pixel_size(24)
            center_lock.add_css_class("dimmed")
            center_box.append(center_lock)
            self.card_box.append(center_box)
            self.set_child(self.card_box)
            return

        # 1. Top Row: Checkbox revealer + Dot + Title + (Pin/Todo Icons)
        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        top_box.set_hexpand(True)

        self.revealer = Gtk.Revealer()
        self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT)
        self.revealer.set_reveal_child(selection_mode)

        self.checkbox = Gtk.CheckButton()
        self.checkbox.set_valign(Gtk.Align.CENTER)
        self.checkbox.connect("toggled", self._on_checkbox_toggled)
        self.revealer.set_child(self.checkbox)
        top_box.append(self.revealer)

        # Category Dot indicator (Image 1 style)
        dot = Gtk.Box()
        dot.add_css_class("note-dot")
        dot.set_valign(Gtk.Align.CENTER)
        dot.set_halign(Gtk.Align.CENTER)
        cat = (self.note.category or "").strip()
        if cat and cat.lower() != "uncategorized":
            c_idx = abs(hash(cat)) % 9
            dot.add_css_class(f"cat-{c_idx}")
        top_box.append(dot)

        # Title
        raw_title = self.note.title or "Untitled Note"
        clean_title = strip_markdown(raw_title) or "Untitled Note"
        self.title_lbl = Gtk.Label(label=clean_title)
        self.title_lbl.add_css_class("note-grid-title")
        self.title_lbl.set_halign(Gtk.Align.FILL)
        self.title_lbl.set_hexpand(True)
        self.title_lbl.set_xalign(0.0)
        self.title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_lbl.set_lines(1)
        self.title_lbl.set_single_line_mode(True)
        self.title_lbl.set_max_width_chars(35)
        top_box.append(self.title_lbl)

        if self.note.is_pinned:
            pin_icon = Gtk.Image.new_from_icon_name("starred-symbolic")
            pin_icon.add_css_class("dimmed")
            pin_icon.set_pixel_size(14)
            top_box.append(pin_icon)

        if self.note.has_todo:
            todo_icon = Gtk.Image.new_from_icon_name("checkbox-checked-symbolic")
            todo_icon.add_css_class("dimmed")
            todo_icon.set_pixel_size(14)
            top_box.append(todo_icon)

        if self.note.is_locked:
            lock_icon = Gtk.Image.new_from_icon_name("channel-secure-symbolic")
            lock_icon.add_css_class("dimmed")
            lock_icon.set_pixel_size(14)
            lock_icon.set_tooltip_text("Private Note")
            top_box.append(lock_icon)

        self.card_box.append(top_box)

        # 2. Date Row: "Monday, 28/09 08:02" (matching Image 1)
        try:
            dt = datetime.fromtimestamp(self.note.updated_at)
            date_str = dt.strftime("%A, %d/%m %H:%M")
        except Exception:
            date_str = ""

        if date_str:
            self.date_lbl = Gtk.Label(label=date_str)
            self.date_lbl.add_css_class("note-grid-date")
            self.date_lbl.set_halign(Gtk.Align.FILL)
            self.date_lbl.set_hexpand(True)
            self.date_lbl.set_xalign(0.0)
            self.date_lbl.set_lines(1)
            self.date_lbl.set_single_line_mode(True)
            self.date_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            self.date_lbl.set_max_width_chars(35)
            self.card_box.append(self.date_lbl)

        # 3. Banner preview: Primary Image or Table Preview
        # Rule: if image + table, then image; if table only, then table preview (partial like image)
        img_bytes = get_note_image_bytes(self.note, self.db)
        self.thumb = None
        self.table_preview = None
        table_data = None

        if img_bytes:
            texture = _create_thumbnail_texture(img_bytes)
            if texture:
                img_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                img_container.set_size_request(100, 75)
                img_container.set_hexpand(True)
                img_container.set_vexpand(False)
                img_container.set_halign(Gtk.Align.FILL)
                img_container.set_valign(Gtk.Align.FILL)
                img_container.set_overflow(Gtk.Overflow.HIDDEN)

                self.thumb = Gtk.Picture.new_for_paintable(texture)
                self.thumb.set_can_shrink(True)
                self.thumb.set_content_fit(Gtk.ContentFit.COVER)
                self.thumb.set_size_request(100, 75)
                self.thumb.set_hexpand(True)
                self.thumb.set_halign(Gtk.Align.FILL)
                self.thumb.add_css_class("note-grid-thumbnail")
                img_container.append(self.thumb)
                self.card_box.append(img_container)
        else:
            table_data = get_note_table_data(self.note, self.db)
            if table_data:
                table_widget = _create_table_preview_widget(table_data)
                if table_widget:
                    self.table_preview = table_widget
                    self.card_box.append(self.table_preview)

        # 4. Body excerpt preview (multi-line)
        preview_text = _get_note_preview(self.note)
        has_media = bool(self.thumb or self.table_preview)
        if has_media and preview_text == "Type text here...":
            preview_text = ""

        # Suppress the body excerpt when a table preview banner is shown, so the
        # banner is the only thing displayed for a table-only card.
        if self.table_preview and preview_text:
            preview_text = ""

        cat = (self.note.category or "").strip()
        has_category = bool(cat and cat.lower() != "uncategorized" and self.show_category_pill)

        self.body_lbl = Gtk.Label(label=preview_text)
        self.body_lbl.add_css_class("note-grid-body")
        self.body_lbl.set_wrap(True)
        self.body_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.body_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        self.body_lbl.set_lines(1 if has_media else 2)
        self.body_lbl.set_halign(Gtk.Align.FILL)
        self.body_lbl.set_hexpand(True)
        self.body_lbl.set_valign(Gtk.Align.START)
        self.body_lbl.set_xalign(0.0)
        self.body_lbl.set_yalign(0.0)
        self.body_lbl.set_vexpand(True)
        self.body_lbl.set_max_width_chars(42)
        self.body_lbl.set_visible(bool(preview_text))
        self.card_box.append(self.body_lbl)

        # 5. Bottom Row: Category pill (anchored to bottom, expands up to card width)
        footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        footer_box.set_valign(Gtk.Align.END)
        footer_box.set_halign(Gtk.Align.FILL)
        footer_box.set_hexpand(True)
        footer_box.set_vexpand(False)

        if has_category:
            self.cat_pill = Gtk.Label(label=cat)
            self.cat_pill.add_css_class("index-category-pill")
            self.cat_pill.set_halign(Gtk.Align.START)
            self.cat_pill.set_xalign(0.0)
            self.cat_pill.set_ellipsize(Pango.EllipsizeMode.END)
            self.cat_pill.set_lines(1)
            self.cat_pill.set_single_line_mode(True)
            self.cat_pill.set_max_width_chars(20)
            self.cat_pill.set_tooltip_text(cat)
            footer_box.append(self.cat_pill)
        else:
            self.cat_pill = None

        self.card_box.append(footer_box)

        self.set_child(self.card_box)

    def _on_checkbox_toggled(self, cb):
        active = cb.get_active()
        if active:
            self.card_box.add_css_class("checked")
        else:
            self.card_box.remove_css_class("checked")
        self.emit("toggled", active)


class NoteListRow(BaseNoteCard):
    __gtype_name__ = "NoteListRow"

    def _build_ui(self, selection_mode: bool):
        self.set_size_request(300, 68)
        self.set_hexpand(True)
        self.set_halign(Gtk.Align.FILL)

        self.card_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.card_box.add_css_class("note-list-card")
        self.card_box.set_hexpand(True)

        if self.is_private_locked:
            self.card_box.add_css_class("locked-note-card")
            self.revealer = Gtk.Revealer()
            self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT)
            self.revealer.set_reveal_child(selection_mode)
            self.checkbox = Gtk.CheckButton()
            self.checkbox.set_valign(Gtk.Align.CENTER)
            self.checkbox.set_margin_end(8)
            self.checkbox.connect("toggled", self._on_checkbox_toggled)
            self.revealer.set_child(self.checkbox)
            self.card_box.append(self.revealer)

            text_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            text_vbox.set_hexpand(True)
            text_vbox.set_valign(Gtk.Align.CENTER)

            title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            lock_icon = Gtk.Image.new_from_icon_name("channel-secure-symbolic")
            lock_icon.add_css_class("dimmed")
            lock_icon.set_pixel_size(14)
            title_box.append(lock_icon)

            self.title_lbl = Gtk.Label(label="Locked Note")
            self.title_lbl.add_css_class("title")
            self.title_lbl.set_halign(Gtk.Align.FILL)
            self.title_lbl.set_xalign(0.0)
            self.title_lbl.set_hexpand(True)
            title_box.append(self.title_lbl)
            text_vbox.append(title_box)

            try:
                dt = datetime.fromtimestamp(self.note.updated_at)
                date_str = dt.strftime("%A, %d/%m %H:%M")
            except Exception:
                date_str = ""
            if date_str:
                self.date_lbl = Gtk.Label(label=date_str)
                self.date_lbl.add_css_class("subtitle")
                self.date_lbl.set_halign(Gtk.Align.START)
                self.date_lbl.set_xalign(0.0)
                text_vbox.append(self.date_lbl)

            self.card_box.append(text_vbox)
            self.set_child(self.card_box)
            return

        # Checkbox revealer for selection mode
        self.revealer = Gtk.Revealer()
        self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT)
        self.revealer.set_reveal_child(selection_mode)

        self.checkbox = Gtk.CheckButton()
        self.checkbox.set_valign(Gtk.Align.CENTER)
        self.checkbox.set_margin_end(8)
        self.checkbox.connect("toggled", self._on_checkbox_toggled)
        self.revealer.set_child(self.checkbox)
        self.card_box.append(self.revealer)

        # Note text column
        text_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        text_vbox.set_hexpand(True)
        text_vbox.set_valign(Gtk.Align.CENTER)

        # Title row: Title Label + Starred Icon
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        raw_title = self.note.title or "Untitled Note"
        clean_title = strip_markdown(raw_title) or "Untitled Note"
        self.title_lbl = Gtk.Label(label=clean_title)
        self.title_lbl.add_css_class("title")
        self.title_lbl.set_halign(Gtk.Align.FILL)
        self.title_lbl.set_xalign(0.0)
        self.title_lbl.set_hexpand(True)
        self.title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_lbl.set_lines(1)
        self.title_lbl.set_single_line_mode(True)
        self.title_lbl.set_max_width_chars(25)
        title_box.append(self.title_lbl)

        if self.note.is_pinned:
            pin_icon = Gtk.Image.new_from_icon_name("starred-symbolic")
            pin_icon.add_css_class("dimmed")
            pin_icon.set_pixel_size(14)
            title_box.append(pin_icon)

        if self.note.is_locked:
            lock_icon = Gtk.Image.new_from_icon_name("channel-secure-symbolic")
            lock_icon.add_css_class("dimmed")
            lock_icon.set_pixel_size(14)
            lock_icon.set_tooltip_text("Private Note")
            title_box.append(lock_icon)

        text_vbox.append(title_box)

        # Subtitle Row: Excerpt + Category pill
        subtitle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        subtitle_box.set_hexpand(True)

        raw_excerpt = self.note.excerpt or "No additional text"
        clean_excerpt = strip_markdown(raw_excerpt) or "No additional text"
        self.excerpt_lbl = Gtk.Label(label=clean_excerpt)
        self.excerpt_lbl.add_css_class("subtitle")
        self.excerpt_lbl.set_halign(Gtk.Align.FILL)
        self.excerpt_lbl.set_xalign(0.0)
        self.excerpt_lbl.set_hexpand(True)
        self.excerpt_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        self.excerpt_lbl.set_lines(1)
        self.excerpt_lbl.set_single_line_mode(True)
        self.excerpt_lbl.set_max_width_chars(20)
        subtitle_box.append(self.excerpt_lbl)

        cat = (self.note.category or "").strip()
        if cat and cat.lower() != "uncategorized" and self.show_category_pill:
            self.cat_pill = Gtk.Label(label=cat)
            self.cat_pill.add_css_class("index-category-pill")
            self.cat_pill.set_halign(Gtk.Align.END)
            self.cat_pill.set_valign(Gtk.Align.CENTER)
            self.cat_pill.set_ellipsize(Pango.EllipsizeMode.END)
            self.cat_pill.set_lines(1)
            self.cat_pill.set_single_line_mode(True)
            self.cat_pill.set_max_width_chars(15)
            self.cat_pill.set_tooltip_text(cat)
            subtitle_box.append(self.cat_pill)
        else:
            self.cat_pill = None

        text_vbox.append(subtitle_box)
        self.card_box.append(text_vbox)

        self.set_child(self.card_box)

    def _on_checkbox_toggled(self, cb):
        active = cb.get_active()
        if active:
            self.card_box.add_css_class("checked")
        else:
            self.card_box.remove_css_class("checked")
        self.emit("toggled", active)


# Aliases for compatibility
IndexRow = NoteListRow
NoteRow = NoteListRow


class NotesList(Gtk.Box):
    __gtype_name__ = "NotesList"

    __gsignals__ = {
        "note-selected": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "locked-note-clicked": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        "note-pin-toggled": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "note-copy-link": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "note-deleted": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "note-duplicated": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "new-note-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "selection-changed": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self, db, view_mode: str = "list"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.db = db
        self.view_mode = view_mode
        self.selection_mode = False
        self.current_notes: List[Note] = []
        self._all_cards: List[BaseNoteCard] = []
        self.is_search = False
        self.active_filter_type = "all"
        self.active_category_name = ""
        self.is_private_unlocked = False

        try:
            from teddynotes.config_manager import ConfigManager
            self.config_manager = ConfigManager.get_default(self.db)
            self.set_card_size(self.config_manager.get_card_font_size())
        except Exception:
            self.set_card_size("default")

        self._build_ui()

    def set_card_size(self, size: str):
        for s in ("small", "default", "large", "xlarge"):
            self.remove_css_class(f"card-size-{s}")
        if size not in ("small", "default", "large", "xlarge"):
            size = "default"
        self.add_css_class(f"card-size-{size}")

    @property
    def _all_rows(self) -> List[BaseNoteCard]:
        return self._all_cards

    @_all_rows.setter
    def _all_rows(self, val):
        self._all_cards = val

    def _build_ui(self):
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # 1. Scrolled Sectioned View
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_vexpand(True)
        self.scrolled.set_hexpand(True)
        # Avoid inertial tail-off when scrolling through long note lists.
        self.scrolled.set_kinetic_scrolling(False)

        self.clamp = Adw.Clamp()
        self.clamp.set_maximum_size(1800)
        self.clamp.set_tightening_threshold(1200)

        # Sections Container
        self.sections_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.sections_box.set_name("Sections")
        self.sections_box.set_margin_top(16)
        self.sections_box.set_margin_bottom(28)
        self.sections_box.set_margin_start(16)
        self.sections_box.set_margin_end(16)

        # 1. Favorites Section
        self.fav_section, self.fav_flowbox = self._create_section("Favorites", has_star=True)
        self.sections_box.append(self.fav_section)

        # 2. Today Section
        self.today_section, self.today_flowbox = self._create_section("Today")
        self.sections_box.append(self.today_section)

        # 3. Yesterday Section
        self.yesterday_section, self.yesterday_flowbox = self._create_section("Yesterday")
        self.sections_box.append(self.yesterday_section)

        # 4. This Week Section
        self.week_section, self.week_flowbox = self._create_section("This Week")
        self.sections_box.append(self.week_section)

        # 5. This Month Section
        self.month_section, self.month_flowbox = self._create_section("This Month")
        self.sections_box.append(self.month_section)

        # 6. Earlier Section
        self.earlier_section, self.earlier_flowbox = self._create_section("Earlier")
        self.sections_box.append(self.earlier_section)

        # 7. Search Results Section (no header)
        self.search_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.search_flowbox = self._create_flowbox()
        self.search_section.append(self.search_flowbox)
        self.sections_box.append(self.search_section)

        self.clamp.set_child(self.sections_box)
        self.scrolled.set_child(self.clamp)
        self.stack.add_named(self.scrolled, "list")

        # 2. Empty Status Page
        self.empty_page = Adw.StatusPage()
        self.empty_page.set_title("Note List Empty")
        self.empty_page.set_description("Capture your ideas, checklists, and notes in markdown.")
        self.empty_page.set_icon_name("text-editor-symbolic")

        self.empty_new_btn = Gtk.Button(label="New Note")
        self.empty_new_btn.add_css_class("pill")
        self.empty_new_btn.add_css_class("suggested-action")
        self.empty_new_btn.set_halign(Gtk.Align.CENTER)
        self.empty_new_btn.connect("clicked", lambda _b: self.emit("new-note-requested"))
        self.empty_page.set_child(self.empty_new_btn)
        self.stack.add_named(self.empty_page, "empty")

        # 3. Search Empty Page
        self.search_empty_page = Adw.StatusPage()
        self.search_empty_page.set_title("No Results Found")
        self.search_empty_page.set_description("Try searching with different keywords.")
        self.search_empty_page.set_icon_name("system-search-symbolic")
        self.stack.add_named(self.search_empty_page, "search_empty")

        self.append(self.stack)

    def _get_spacing(self):
        col_spacing = 8 if self.view_mode == "grid" else 6
        row_spacing = 8 if self.view_mode == "grid" else 6
        return col_spacing, row_spacing

    def _get_all_flowboxes(self) -> List[Gtk.FlowBox]:
        return [
            self.fav_flowbox,
            self.today_flowbox,
            self.yesterday_flowbox,
            self.week_flowbox,
            self.month_flowbox,
            self.earlier_flowbox,
            self.search_flowbox
        ]

    def _create_flowbox(self) -> Gtk.FlowBox:
        flowbox = Gtk.FlowBox()
        flowbox.set_homogeneous(True)
        flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        flowbox.set_activate_on_single_click(True)
        col_sp, row_sp = self._get_spacing()
        flowbox.set_column_spacing(col_sp)
        flowbox.set_row_spacing(row_sp)
        flowbox.set_min_children_per_line(1)
        flowbox.set_max_children_per_line(24 if self.view_mode == "grid" else 3)
        flowbox.set_valign(Gtk.Align.START)
        flowbox.set_halign(Gtk.Align.FILL)
        flowbox.set_hexpand(True)
        flowbox.add_css_class("notes-flowbox")
        flowbox.connect("child-activated", self._on_child_activated)
        return flowbox

    def _create_section(self, title: str, has_star: bool = False):
        sec_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl = Gtk.Label(label=title)
        lbl.add_css_class("index-section-title")
        lbl.add_css_class("heading")
        lbl.add_css_class("h4")
        lbl.set_halign(Gtk.Align.START)
        lbl.set_xalign(0.0)
        lbl.set_single_line_mode(True)
        lbl.set_lines(1)
        header_box.append(lbl)

        if has_star:
            star_img = Gtk.Image.new_from_icon_name("starred-symbolic")
            star_img.add_css_class("index-section")
            star_img.add_css_class("dimmed")
            star_img.set_pixel_size(16)
            star_img.set_valign(Gtk.Align.CENTER)
            header_box.append(star_img)

        sec_box.append(header_box)

        flowbox = self._create_flowbox()
        sec_box.append(flowbox)

        return sec_box, flowbox

    def set_view_mode(self, mode: str):
        if mode not in ("list", "grid"):
            mode = "list"
        if self.view_mode != mode:
            self.view_mode = mode
            col_sp, row_sp = self._get_spacing()
            max_children = 24 if mode == "grid" else 3
            for fb in self._get_all_flowboxes():
                fb.set_column_spacing(col_sp)
                fb.set_row_spacing(row_sp)
                fb.set_max_children_per_line(max_children)
            self.set_notes(
                self.current_notes,
                is_search=self.is_search,
                active_filter_type=self.active_filter_type,
                active_category_name=self.active_category_name,
                is_private_unlocked=self.is_private_unlocked
            )

    def _clear_flowbox(self, flowbox: Gtk.FlowBox):
        flowbox.remove_all()

    def set_notes(
        self,
        notes: List[Note],
        is_search: bool = False,
        active_filter_type: str = "all",
        active_category_name: str = "",
        is_private_unlocked: bool = False
    ):
        self.current_notes = notes
        self.is_search = is_search
        self.active_filter_type = active_filter_type
        self.active_category_name = active_category_name
        self.is_private_unlocked = is_private_unlocked
        self._all_cards.clear()

        # Clear all section flowboxes
        for fb in [
            self.fav_flowbox,
            self.today_flowbox,
            self.yesterday_flowbox,
            self.week_flowbox,
            self.month_flowbox,
            self.earlier_flowbox,
            self.search_flowbox
        ]:
            self._clear_flowbox(fb)

        if not notes:
            if is_search:
                self.stack.set_visible_child_name("search_empty")
            else:
                if active_filter_type == "trash":
                    self.empty_page.set_title("Trash is Empty")
                    self.empty_page.set_description("")
                    self.empty_page.set_icon_name("user-trash-symbolic")
                    self.empty_new_btn.set_visible(False)
                elif active_filter_type in ("private", "locked"):
                    self.empty_page.set_title("No Private Notes")
                    self.empty_page.set_description("Notes locked as private will appear here.")
                    self.empty_page.set_icon_name("channel-secure-symbolic")
                    self.empty_new_btn.set_label("New Private Note")
                    self.empty_new_btn.set_visible(True)
                elif active_filter_type in ("linked", "link", "links"):
                    self.empty_page.set_title("No Linked Notes")
                    self.empty_page.set_description("Notes containing internal or external links will appear here.")
                    self.empty_page.set_icon_name("insert-link-symbolic")
                    self.empty_new_btn.set_label("New Note")
                    self.empty_new_btn.set_visible(True)
                else:
                    self.empty_page.set_title("Note List Empty")
                    self.empty_page.set_description("Capture your ideas, checklists, and notes in markdown.")
                    self.empty_page.set_icon_name("text-editor-symbolic")
                    self.empty_new_btn.set_label("New Note")
                    self.empty_new_btn.set_visible(True)
                self.stack.set_visible_child_name("empty")
            return

        self.stack.set_visible_child_name("list")
        show_pill = True

        if is_search:
            # Hide all date sections, populate search section
            self.fav_section.set_visible(False)
            self.today_section.set_visible(False)
            self.yesterday_section.set_visible(False)
            self.week_section.set_visible(False)
            self.month_section.set_visible(False)
            self.earlier_section.set_visible(False)
            self.search_section.set_visible(True)

            for note in notes:
                is_card_locked = bool(note.is_locked and not is_private_unlocked)
                card = self._create_card(note, show_category_pill=show_pill, is_private_locked=is_card_locked)
                self.search_flowbox.append(card)
            return

        # Regular chronological section grouping
        self.search_section.set_visible(False)

        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        yesterday_start = today_start - 86400
        week_start = (now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())).timestamp()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()

        # Favorites bucket: in All Notes, Recent, Private, Todos, Lists, and Linked views, do not show a separate Favorites section; sort all notes by date
        if active_filter_type in ("all", "recent", "recents", "private", "locked", "todo", "todos", "list", "lists", "linked", "link", "links", None, ""):
            fav_notes = []
            date_notes = notes
        else:
            fav_notes = [n for n in notes if n.is_pinned]
            date_notes = [n for n in notes if not n.is_pinned]

        today_notes = []
        yesterday_notes = []
        week_notes = []
        month_notes = []
        earlier_notes = []

        for n in date_notes:
            t = n.updated_at
            if t >= today_start:
                today_notes.append(n)
            elif t >= yesterday_start:
                yesterday_notes.append(n)
            elif t >= week_start:
                week_notes.append(n)
            elif t >= month_start:
                month_notes.append(n)
            else:
                earlier_notes.append(n)

        sections_data = [
            (self.fav_section, self.fav_flowbox, fav_notes),
            (self.today_section, self.today_flowbox, today_notes),
            (self.yesterday_section, self.yesterday_flowbox, yesterday_notes),
            (self.week_section, self.week_flowbox, week_notes),
            (self.month_section, self.month_flowbox, month_notes),
            (self.earlier_section, self.earlier_flowbox, earlier_notes),
        ]

        for sec_widget, flowbox, n_list in sections_data:
            if n_list:
                sec_widget.set_visible(True)
                for note in n_list:
                    is_card_locked = bool(note.is_locked and not is_private_unlocked)
                    card = self._create_card(note, show_category_pill=show_pill, is_private_locked=is_card_locked)
                    flowbox.append(card)
            else:
                sec_widget.set_visible(False)

    def _create_card(self, note: Note, show_category_pill: bool = True, is_private_locked: bool = False) -> BaseNoteCard:
        if self.view_mode == "grid":
            card = NoteGridCard(note, db=self.db, selection_mode=self.selection_mode, show_category_pill=show_category_pill, is_private_locked=is_private_locked)
        else:
            card = NoteListRow(note, db=self.db, selection_mode=self.selection_mode, show_category_pill=show_category_pill, is_private_locked=is_private_locked)

        card.connect("pin-toggled", lambda _r, nid: self.emit("note-pin-toggled", nid))
        card.connect("copy-link", lambda _r, nid: self.emit("note-copy-link", nid))
        card.connect("duplicate", lambda _r, nid: self.emit("note-duplicated", nid))
        card.connect("delete", lambda _r, nid: self.emit("note-deleted", nid))
        card.connect("restore", lambda _r, nid: self._on_restore(nid))
        card.connect("perm-delete", lambda _r, nid: self._on_perm_delete(nid))
        card.connect("toggled", lambda _r, _a: self.emit("selection-changed", len(self.get_checked_notes())))
        self._all_cards.append(card)
        return card

    def _create_row(self, note: Note, show_category_pill: bool = True) -> BaseNoteCard:
        """Alias for backward compatibility."""
        return self._create_card(note, show_category_pill=show_category_pill)

    def _on_restore(self, note_id: str):
        self.db.restore_note(note_id)
        self.emit("note-pin-toggled", note_id)

    def _on_perm_delete(self, note_id: str):
        self.db.delete_note(note_id, permanent=True)
        self.emit("note-pin-toggled", note_id)

    def _on_child_activated(self, flowbox: Gtk.FlowBox, child: BaseNoteCard):
        if not child:
            return
        flowbox.unselect_all()
        if self.selection_mode:
            child.set_checked(not child.is_checked())
        else:
            if getattr(child, "is_private_locked", False):
                self.emit("locked-note-clicked", child.note)
            else:
                self.emit("note-selected", child.note)

    def _on_row_activated(self, flowbox, child):
        """Alias for backward compatibility."""
        self._on_child_activated(flowbox, child)

    def set_selection_mode(self, enabled: bool):
        self.selection_mode = enabled
        for card in self._all_cards:
            card.set_selection_mode(enabled)
            if not enabled:
                card.set_checked(False)
        if not enabled:
            self.emit("selection-changed", 0)

    def get_checked_notes(self) -> List[Note]:
        return [card.note for card in self._all_cards if card.is_checked()]

    def select_all(self, checked: bool = True):
        for card in self._all_cards:
            card.set_checked(checked)
        self.emit("selection-changed", len(self.get_checked_notes()))

    def clear_all_checkboxes(self):
        for card in self._all_cards:
            card.set_checked(False)
        self.emit("selection-changed", 0)
