# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import urllib.parse
from pathlib import Path
from typing import Any, Optional, List
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, Gio, GLib, GObject

from teddynotes.models import Note
from teddynotes.database import NoteDatabase
from teddynotes.config_manager import ConfigManager
from teddynotes.index import IndexView
from teddynotes.editor import NoteEditor
from teddynotes.const import APP_ID, IS_DEVEL

class TeddyWindow(Adw.ApplicationWindow):
    __gtype_name__ = "TeddyWindow"

    def __init__(self, app: Optional[Adw.Application] = None, db: Optional[NoteDatabase] = None, application: Optional[Adw.Application] = None, **kwargs):
        effective_app = application if application is not None else app
        super().__init__(application=effective_app, **kwargs)
        self.db = db
        self.config_manager = ConfigManager.get_default(db)
        self._pending_sidebar_width = None
        self._sidebar_resize_idle_id = None
        self._note_history: List[str] = []
        self._cleaned_up = False

        self.set_title("Teddy Notes")
        self.set_icon_name(APP_ID)
        self.add_css_class("stilo-window")
        if IS_DEVEL:
            self.add_css_class("devel")

        self._build_ui()
        self._setup_actions()
        self._setup_theme()
        self._restore_session()
        self.db.add_change_listener(self._on_db_changed)

    def _build_ui(self):
        self.split_view = Adw.OverlaySplitView()
        sidebar_w = self.config_manager.get_sidebar_width()
        if hasattr(Adw, "LengthUnit") and hasattr(self.split_view, "set_sidebar_width_unit"):
            self.split_view.set_sidebar_width_unit(Adw.LengthUnit.PX)
        self.split_view.set_min_sidebar_width(sidebar_w)
        self.split_view.set_max_sidebar_width(sidebar_w)
        self.split_view.set_sidebar_width_fraction(0.3)
        self.split_view.set_collapsed(False)
        self.split_view.set_show_sidebar(True)
        self.split_view.set_pin_sidebar(True)

        # 1. Sidebar
        from teddynotes.sidebar import Sidebar
        self.sidebar = Sidebar(self.db)
        self.sidebar.connect("filter-changed", self.on_sidebar_filter_changed)
        self.sidebar.connect("close-requested", lambda _sb: GLib.idle_add(self.split_view.set_show_sidebar, False))
        self.sidebar.connect("width-dragged", self._on_sidebar_width_dragged)
        self.sidebar.connect("width-drag-ended", self._on_sidebar_width_drag_ended)
        self.split_view.set_sidebar(self.sidebar)

        # 2. Content Navigation
        self.navigation = Adw.NavigationView()

        # 2a. Index Page (Notes List)
        self.index_view = IndexView(self.db, sidebar=self.sidebar)
        self.index_view.connect("note-opened", self._on_note_opened)
        self.index_view.connect("create-note", self._on_create_note)

        self.index_page = Adw.NavigationPage.new(self.index_view, "Notes")
        self.index_page.connect("shown", lambda _p: self.index_view.refresh(update_sidebar=True))
        self.navigation.add(self.index_page)

        # 2b. Editor Page
        self.editor = NoteEditor(self.db)
        self.editor.setup_actions(self)
        self.editor.connect("note-updated", self._on_note_updated)
        self.editor.connect("note-deleted", self._on_editor_note_deleted)
        self.editor.connect("note-pin-toggled", self._on_editor_note_pin_toggled)
        self.editor.connect("note-duplicated", self._on_editor_note_duplicated)
        self.editor.connect("note-category-changed", self._on_editor_category_changed)
        self.editor.connect("tag-clicked", self._on_editor_tag_clicked)
        self.editor.connect("open-note-link", self._on_editor_open_note_link)
        self.editor.connect("back", self._on_editor_back)
        self.editor.connect("toggle-sidebar", lambda _ed: self.toggle_sidebar())
        self.editor.connect("toggle-app-theme", lambda _ed: self._toggle_theme())

        self.editor_page = Adw.NavigationPage.new(self.editor, "Editor")
        self.editor_page.set_can_pop(True)
        self.editor_page.connect("shown", lambda _p: self.editor.focus_editor())
        self.navigation.add(self.editor_page)

        self.split_view.set_content(self.navigation)
        self.set_content(self.split_view)

        self._setup_breakpoint()

        # Connect close-request and destroy to cleanly release resources and remember state
        self.connect("close-request", self._on_close_request)
        self.connect("destroy", self._on_destroy)

    def apply_editor_mode(self, mode: str):
        """Update sidebar visibility based on editor_mode without reparenting containers."""
        is_editor = (self.navigation.get_visible_page() == self.editor_page)
        if is_editor:
            if mode == "distraction_free":
                self.split_view.set_show_sidebar(False)
            else:
                if not self.split_view.get_collapsed():
                    self.split_view.set_show_sidebar(True)
        else:
            if not self.split_view.get_collapsed():
                self.split_view.set_show_sidebar(True)

    def _setup_breakpoint(self):
        cond = Adw.breakpoint_condition_parse("max-width: 700sp")
        bp = Adw.Breakpoint.new(cond)
        bp.connect("apply", self._on_breakpoint_apply)
        bp.connect("unapply", self._on_breakpoint_unapply)
        self.add_breakpoint(bp)

        self._update_responsive_state(is_collapsed=False)

    def _on_breakpoint_apply(self, _bp):
        self.split_view.set_pin_sidebar(False)
        self.split_view.set_collapsed(True)
        self.split_view.set_show_sidebar(False)
        self.sidebar.set_resizer_visible(False)
        self._update_responsive_state(is_collapsed=True)

    def _on_breakpoint_unapply(self, _bp):
        self.split_view.set_pin_sidebar(True)
        self.split_view.set_collapsed(False)
        self.sidebar.set_resizer_visible(True)
        is_editor = (self.navigation.get_visible_page() == self.editor_page)
        if is_editor and self.config_manager.get_editor_mode() == "distraction_free":
            self.split_view.set_show_sidebar(False)
        else:
            self.split_view.set_show_sidebar(True)
        self._update_responsive_state(is_collapsed=False)

    def _update_responsive_state(self, is_collapsed: bool):
        self.index_view.update_header_buttons(is_collapsed)

    def _on_sidebar_width_dragged(self, _sb, new_width: int):
        self._pending_sidebar_width = new_width
        if self._sidebar_resize_idle_id is None:
            self._sidebar_resize_idle_id = GLib.idle_add(
                self._apply_pending_sidebar_width,
                priority=GLib.PRIORITY_DEFAULT_IDLE
            )

    def _on_sidebar_width_drag_ended(self, _sb, final_width: int):
        self._pending_sidebar_width = final_width
        self._flush_pending_sidebar_resize()

    def _flush_pending_sidebar_resize(self):
        if self._sidebar_resize_idle_id is not None:
            GLib.source_remove(self._sidebar_resize_idle_id)
            self._sidebar_resize_idle_id = None
        self._apply_pending_sidebar_width()

    def _apply_pending_sidebar_width(self) -> bool:
        self._sidebar_resize_idle_id = None
        new_width = self._pending_sidebar_width
        if new_width is None:
            return GLib.SOURCE_REMOVE

        cur_min = int(self.split_view.get_min_sidebar_width())
        cur_max = int(self.split_view.get_max_sidebar_width())

        if new_width == cur_min and new_width == cur_max:
            return GLib.SOURCE_REMOVE

        # Order updates so min_sidebar_width is never greater than max_sidebar_width
        if new_width > cur_max:
            self.split_view.set_max_sidebar_width(new_width)
            self.split_view.set_min_sidebar_width(new_width)
        else:
            self.split_view.set_min_sidebar_width(new_width)
            self.split_view.set_max_sidebar_width(new_width)

        total_w = self.split_view.get_allocated_width() or self.get_width()
        if total_w > 0:
            self.split_view.set_sidebar_width_fraction(new_width / total_w)

        return GLib.SOURCE_REMOVE

    def toggle_sidebar(self):
        mode = self.config_manager.get_editor_mode()
        if mode == "distraction_free" and self.navigation.get_visible_page() == self.editor_page:
            self._go_back()
            return
        is_show = self.split_view.get_show_sidebar()
        self.split_view.set_show_sidebar(not is_show)

    def on_sidebar_filter_changed(self, *args, **kwargs):
        if self.navigation.get_visible_page() == self.editor_page:
            self._go_back()
        if self.split_view.get_collapsed():
            GLib.idle_add(self.split_view.set_show_sidebar, False)

    def apply_card_size(self, size: str):
        if hasattr(self, "index_view") and hasattr(self.index_view, "notes_list"):
            self.index_view.notes_list.set_card_size(size)

    def _setup_actions(self):
        action_group = Gio.SimpleActionGroup()

        # Create note
        act_create = Gio.SimpleAction.new("create-note", None)
        act_create.connect("activate", lambda _a, _p: self._on_create_note(None))
        action_group.add_action(act_create)
        self.get_application().set_accels_for_action("win.create-note", ["<Control>n"])

        # Open note from file
        act_open = Gio.SimpleAction.new("open-file", None)
        act_open.connect("activate", lambda _a, _p: self.open_file_dialog())
        action_group.add_action(act_open)
        self.get_application().set_accels_for_action("win.open-file", ["<Control>o"])

        # Search
        act_search = Gio.SimpleAction.new("search", None)
        act_search.connect("activate", lambda _a, _p: self.index_view.enter_search())
        action_group.add_action(act_search)
        self.get_application().set_accels_for_action("win.search", ["<Control>f"])

        # Go back
        act_back = Gio.SimpleAction.new("go-back", None)
        act_back.connect("activate", lambda _a, _p: self._go_back())
        action_group.add_action(act_back)
        self.get_application().set_accels_for_action("win.go-back", ["Escape", "<Alt>Left"])

        # Toggle sidebar
        act_sidebar = Gio.SimpleAction.new("toggle-sidebar", None)
        act_sidebar.connect("activate", lambda _a, _p: self.toggle_sidebar())
        action_group.add_action(act_sidebar)
        self.get_application().set_accels_for_action("win.toggle-sidebar", ["<Control>backslash", "F11"])

        # Toggle Theme
        act_theme = Gio.SimpleAction.new("toggle-theme", None)
        act_theme.connect("activate", lambda _a, _p: self._toggle_theme())
        action_group.add_action(act_theme)
        self.get_application().set_accels_for_action("win.toggle-theme", ["<Control><Shift>d"])

        # Toggle View Mode (List / Grid)
        act_view_mode = Gio.SimpleAction.new("toggle-view-mode", None)
        act_view_mode.connect("activate", lambda _a, _p: self.index_view.toggle_view_mode())
        action_group.add_action(act_view_mode)
        self.get_application().set_accels_for_action("win.toggle-view-mode", ["<Control>g"])

        # Print Note
        act_print = Gio.SimpleAction.new("print", None)
        act_print.connect("activate", lambda _a, _p: self._on_print())
        action_group.add_action(act_print)
        self.get_application().set_accels_for_action("win.print", ["<Control>p"])

        # Page Setup
        act_page_setup = Gio.SimpleAction.new("page-setup", None)
        act_page_setup.connect("activate", lambda _a, _p: self._on_page_setup())
        action_group.add_action(act_page_setup)
        self.get_application().set_accels_for_action("win.page-setup", ["<Control><Shift>p"])

        self.insert_action_group("win", action_group)

    def insert_action_group(self, name: str, group: Optional[Gio.ActionGroup]):
        if not hasattr(self, "_action_groups"):
            self._action_groups = {}
        if group is not None:
            self._action_groups[name] = group
        else:
            self._action_groups.pop(name, None)
        super().insert_action_group(name, group)

    def get_action_group(self, name: str) -> Optional[Gio.ActionGroup]:
        return getattr(self, "_action_groups", {}).get(name)

    def _on_print(self):
        if hasattr(self, "editor") and self.editor and self.editor.current_note:
            self.editor._print_note(self)

    def _on_page_setup(self):
        if hasattr(self, "editor") and self.editor:
            self.editor._on_page_setup(self)

    def _setup_theme(self):
        style_manager = Adw.StyleManager.get_default()
        mode = self.config_manager.get_theme_mode()

        if mode == "dark":
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        elif mode == "light":
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        else:
            style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

        is_dark = style_manager.get_dark()
        self.editor.update_theme(is_dark)

        style_manager.connect("notify::dark", lambda sm, _p: self.editor.update_theme(sm.get_dark()))

    def _toggle_theme(self):
        style_manager = Adw.StyleManager.get_default()
        is_dark = not style_manager.get_dark()
        scheme = Adw.ColorScheme.FORCE_DARK if is_dark else Adw.ColorScheme.FORCE_LIGHT
        style_manager.set_color_scheme(scheme)
        self.config_manager.set_theme_mode("dark" if is_dark else "light")
        self.editor.update_theme(is_dark)
        if hasattr(self.editor, "theme_selector"):
            self.editor.theme_selector.populate()

    def _restore_session(self):
        w, h = self.config_manager.get_window_size()
        self.set_default_size(w, h)
        if self.config_manager.get_window_maximized():
            self.maximize()
        # Always start on All Notes view (do not auto-open or create notes on launch)
        self.config_manager.set_last_opened_note_id("")

    def _cleanup(self):
        """Release timers, DB listeners, and child resources cleanly.

        Idempotent: both ``close-request`` and ``destroy`` call this, and the
        second invocation must not double-free timers/handlers.
        """
        if getattr(self, "_cleaned_up", False):
            return
        self._cleaned_up = True
        self._flush_pending_sidebar_resize()
        if hasattr(self, "db") and self.db:
            try:
                self.db.remove_change_listener(self._on_db_changed)
            except Exception:
                pass
        if hasattr(self, "editor") and self.editor:
            self.editor.destroy_editor()
        if hasattr(self, "index_view") and self.index_view:
            self.index_view.destroy_view()

    def _on_destroy(self, _win):
        self._cleanup()

    def _on_close_request(self, _win):
        self._cleanup()
        # Save window geometry
        w = self.get_width()
        h = self.get_height()
        self.config_manager.set_window_size(w, h)
        self.config_manager.set_window_maximized(self.is_maximized())
        return False

    def open_note(self, note: Note, immediate: bool = False, is_new: bool = False, preserve_history: bool = False):
        """Open a note in the editor and navigate to it."""
        if not preserve_history and hasattr(self, "_note_history"):
            self._note_history.clear()

        full_note = self.db.get_note(note.id)
        target = full_note or note
        if getattr(target, "is_locked", False) and not getattr(self.index_view, "_private_unlocked", False):
            self.index_view._prompt_unlock_private(target_note=target)
            return

        self.editor.load_note(target, is_new=is_new)
        self.editor.update_back_tooltip(bool(getattr(self, "_note_history", None)))
        self.config_manager.set_last_opened_note_id(note.id)

        visible_page = self.navigation.get_visible_page()
        if visible_page != self.editor_page:
            self.navigation.push(self.editor_page)

        if self.config_manager.get_editor_mode() == "distraction_free":
            self.split_view.set_show_sidebar(False)
        else:
            if not self.split_view.get_collapsed():
                self.split_view.set_show_sidebar(True)

    def _on_note_opened(self, _iv, note: Note, immediate: bool):
        self.open_note(note, immediate, is_new=False)

    def _on_create_note(self, _iv):
        category = self.index_view.active_category_name if self.index_view.active_filter_type == "category" else ""
        is_locked = (self.index_view.active_filter_type in ("private", "locked"))
        if is_locked and not getattr(self.index_view, "_private_unlocked", False):
            def create_after_unlock():
                note = self.db.create_note(category=category, is_locked=True, sender=self)
                self.index_view.refresh()
                full_note = self.db.get_note(note.id)
                self.open_note(full_note or note, immediate=False, is_new=True)
            self.index_view._prompt_unlock_private(on_unlocked=create_after_unlock)
            return

        note = self.db.create_note(category=category, is_locked=is_locked, sender=self)
        self.index_view.refresh()
        full_note = self.db.get_note(note.id)
        self.open_note(full_note or note, immediate=False, is_new=True)

    def open_file_dialog(self):
        """Open a .md or .txt file and load it as a note."""
        file_dialog = Gtk.FileDialog()
        file_dialog.set_title("Open Note from File")

        filters = Gio.ListStore.new(Gtk.FileFilter)

        f_notes = Gtk.FileFilter()
        f_notes.set_name("Notes (*.md, *.txt, *.markdown)")
        f_notes.add_pattern("*.md")
        f_notes.add_pattern("*.txt")
        f_notes.add_pattern("*.markdown")
        filters.append(f_notes)

        f_md = Gtk.FileFilter()
        f_md.set_name("Markdown Files (*.md, *.markdown)")
        f_md.add_pattern("*.md")
        f_md.add_pattern("*.markdown")
        filters.append(f_md)

        f_txt = Gtk.FileFilter()
        f_txt.set_name("Text Files (*.txt)")
        f_txt.add_pattern("*.txt")
        filters.append(f_txt)

        f_all = Gtk.FileFilter()
        f_all.set_name("All Files (*)")
        f_all.add_pattern("*")
        filters.append(f_all)

        file_dialog.set_filters(filters)
        file_dialog.set_default_filter(f_notes)

        def on_open_finish(fd, res):
            try:
                gfile = fd.open_finish(res)
                if not gfile:
                    return
                target_path = gfile.get_path()
                if not target_path:
                    uri = gfile.get_uri() or ""
                    if uri.startswith("file://"):
                        target_path = urllib.parse.unquote(uri[7:])
                if target_path and os.path.exists(target_path):
                    self.load_note_from_file(target_path)
            except Exception as e:
                print("Open file cancelled or failed:", e)

        file_dialog.open(self, None, on_open_finish)

    def load_note_from_file(self, file_path: str) -> Optional[Note]:
        """Load a .md or .txt file into the database, refresh views and open in editor."""
        note = self.db.import_note_from_file(file_path, sender=self)
        self.index_view.refresh(update_sidebar=True)
        if hasattr(self, "sidebar"):
            self.sidebar.refresh()
        full_note = self.db.get_note(note.id) or note
        self.open_note(full_note)
        if hasattr(self.index_view, "toast_overlay"):
            p = Path(file_path)
            self.index_view.toast_overlay.add_toast(
                Adw.Toast.new(f"Loaded note '{note.title}' from {p.name}")
            )
        return full_note

    def _on_note_updated(self, _ed, note_id: str, title: str, excerpt: str, html: str, md: str, tags: list, has_todo: bool):
        if hasattr(self, "sidebar"):
            self.sidebar.refresh()
        if hasattr(self, "editor"):
            self.editor._sync_autocomplete_data()
        if self.navigation.get_visible_page() != self.editor_page:
            self.index_view.refresh(update_sidebar=False)

    def _on_editor_note_deleted(self, _ed, note_id: str):
        self.db.delete_note(note_id, sender=self)
        if hasattr(self, "_note_history"):
            self._note_history.clear()
        self._go_back()
        self.index_view.refresh(update_sidebar=True)

    def _on_editor_note_pin_toggled(self, _ed, note_id: str):
        self.db.toggle_pin_note(note_id, sender=self)
        # Reflect current note pin state in the star button
        if self.editor.current_note and self.editor.current_note.id == note_id:
            self.editor._update_star_btn(self.editor.current_note.is_pinned)
        self.index_view.refresh(update_sidebar=True)

    def _on_editor_note_duplicated(self, _ed, note_id: str):
        dup = self.db.duplicate_note(note_id)
        self.index_view.refresh(update_sidebar=True)
        if dup:
            self.open_note(dup, immediate=False)

    def _on_db_changed(self, event_type: str, data: dict, sender: Any):
        # Ignore events originating from this window or its child components
        if sender in (self, getattr(self, "editor", None), getattr(self, "index_view", None)):
            return

        is_in_editor = (self.navigation.get_visible_page() == self.editor_page)
        curr_note = self.editor.current_note if hasattr(self, "editor") else None
        curr_note_id = curr_note.id if curr_note else None

        if event_type == "note-saved":
            note_id = data.get("note_id")
            if is_in_editor and curr_note_id == note_id:
                # Same note is open in this window!
                if self.editor.has_pending_changes():
                    # Local window has pending unsaved changes -> show conflict banner
                    self.editor.show_conflict_banner()
                else:
                    # Clean reload from DB
                    full = self.db.get_note(note_id)
                    if full:
                        self.editor.reload_note_from_db(full)
            else:
                self.index_view.refresh(update_sidebar=True)
                if is_in_editor:
                    self.editor._sync_autocomplete_data()

        elif event_type in ("note-deleted", "notes-deleted"):
            deleted_ids = [data.get("note_id")] if event_type == "note-deleted" else data.get("note_ids", [])
            if is_in_editor and curr_note_id in deleted_ids:
                is_perm = data.get("permanent", False)
                self._go_back()
                msg = "Note permanently deleted in another window" if is_perm else "Note moved to trash in another window"
                self.index_view.toast_overlay.add_toast(Adw.Toast.new(msg))
            self.index_view.refresh(update_sidebar=True)

        elif event_type == "trash-emptied":
            if is_in_editor and curr_note and curr_note.is_trashed:
                self._go_back()
                self.index_view.toast_overlay.add_toast(Adw.Toast.new("Trash was emptied in another window"))
            self.index_view.refresh(update_sidebar=True)

        elif event_type in ("note-restored", "notes-restored"):
            restored_ids = [data.get("note_id")] if event_type == "note-restored" else data.get("note_ids", [])
            if is_in_editor and curr_note_id in restored_ids:
                if self.editor.current_note:
                    self.editor.current_note.is_trashed = False
            self.index_view.refresh(update_sidebar=True)

        elif event_type == "note-pin-toggled":
            pinned_id = data.get("note_id")
            if is_in_editor and curr_note_id == pinned_id:
                is_pinned = data.get("is_pinned")
                if is_pinned is not None:
                    self.editor.current_note.is_pinned = is_pinned
                    self.editor._update_star_btn(is_pinned)
            self.index_view.refresh(update_sidebar=True)

        elif event_type == "note-lock-toggled":
            locked_id = data.get("note_id")
            if is_in_editor and curr_note_id == locked_id:
                is_locked = data.get("is_locked")
                if is_locked is not None:
                    self.editor.current_note.is_locked = is_locked
                    self.editor._update_lock_ui()
            self.index_view.refresh(update_sidebar=True)

        elif event_type in ("category-changed", "categories-updated"):
            if is_in_editor and curr_note_id:
                full = self.db.get_note(curr_note_id)
                if full:
                    self.editor.current_note.category = full.category
                    self.editor.category_header_bar.set_category(full.category)
                self.editor._sync_autocomplete_data()
            self.index_view.refresh(update_sidebar=True)

        elif event_type == "database-restored":
            if is_in_editor:
                self._go_back()
            if hasattr(self, "index_view"):
                self.index_view._private_unlocked = False
            self.index_view.refresh(update_sidebar=True)

    def _on_editor_category_changed(self, _ed, note_id: str, new_category: str):
        self.index_view.refresh(update_sidebar=True)

    def _on_editor_tag_clicked(self, _ed, tag_name: str):
        self._go_back()
        self.index_view.filter_by_tag(tag_name)

    def _on_editor_open_note_link(self, _ed, note_title: str, note_heading: str):
        if not note_title and note_heading:
            self.editor.scroll_to_heading(note_heading)
            return

        target = self.db.find_note_by_title(note_title)
        if not target:
            target = self.db.create_note(title=note_title, initial_text=f"# {note_title}\n\n")
            self.index_view.refresh()

        curr_note = self.editor.current_note
        if curr_note and target and curr_note.id == target.id:
            if note_heading:
                self.editor.scroll_to_heading(note_heading)
            return

        if curr_note and curr_note.id != target.id:
            if hasattr(self, "_note_history"):
                self._note_history.append(curr_note.id)

        self.open_note(target, preserve_history=True)
        if note_heading:
            GLib.idle_add(self.editor.scroll_to_heading, note_heading)

    def _on_editor_back(self, _ed):
        self._go_back()

    def _go_back(self):
        if self.navigation.get_visible_page() == self.editor_page:
            if hasattr(self.editor, "header_stack") and self.editor.header_stack.get_visible_child_name() == "category":
                self.editor.header_stack.set_visible_child_name("main")
                return

            while getattr(self, "_note_history", None):
                prev_id = self._note_history.pop()
                prev_note = self.db.get_note(prev_id)
                if prev_note and not prev_note.is_trashed:
                    self.open_note(prev_note, preserve_history=True)
                    return

            self.editor.flush_save()
            self.navigation.pop()
            if not self.split_view.get_collapsed():
                self.split_view.set_show_sidebar(True)
            self.config_manager.set_last_opened_note_id("")
            self.index_view.refresh(update_sidebar=True)

StiloWindow = TeddyWindow
