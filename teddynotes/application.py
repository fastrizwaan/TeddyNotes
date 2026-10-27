# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import sys
import threading
import time
import tempfile
import urllib.parse
from pathlib import Path
from typing import Optional
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, Gio, Gdk, GLib

from teddynotes.const import APP_ID, APP_NAME, VERSION, get_assets_path
from teddynotes.database import NoteDatabase
from teddynotes.config_manager import ConfigManager
from teddynotes import backup_encryption
from teddynotes.window import TeddyWindow

class TeddyApplication(Adw.Application):
    __gtype_name__ = "TeddyApplication"

    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS
        )
        self.db: Optional[NoteDatabase] = None
        self.config_manager: Optional[ConfigManager] = None

    def create_window(self) -> TeddyWindow:
        """Create and return a new application window sharing the database and config."""
        if not self.db:
            self.db = NoteDatabase()
        if not self.config_manager:
            self.config_manager = ConfigManager.get_default(self.db)
        return TeddyWindow(self, self.db)

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._setup_icons()
        self._load_css()
        self._setup_actions()
        from teddynotes.exporter import setup_print_preview_settings
        setup_print_preview_settings()

    def _setup_icons(self):
        display = Gdk.Display.get_default()
        if display:
            icon_theme = Gtk.IconTheme.get_for_display(display)
            icons_dir = get_assets_path() / "icons"
            if icons_dir.exists():
                icon_theme.add_search_path(str(icons_dir))

            appdir = os.environ.get("APPDIR")
            if appdir:
                icons_root = Path(appdir) / "usr" / "share" / "icons"
                if icons_root.exists():
                    icon_theme.add_search_path(str(icons_root))
                for theme_name in ["hicolor", "Adwaita", "AdwaitaLegacy"]:
                    for sub in ["", "symbolic/apps", "symbolic/actions", "symbolic/status", "symbolic/ui", "scalable/apps"]:
                        d = icons_root / theme_name / sub if sub else icons_root / theme_name
                        if d.exists():
                            icon_theme.add_search_path(str(d))

    def do_activate(self):
        if not self.db:
            self.db = NoteDatabase()
        self.config_manager = ConfigManager.get_default(self.db)

        windows = self.get_windows()
        if not windows:
            win = self.create_window()
            win.present()
        else:
            active_win = self.get_active_window() or windows[0]
            active_win.present()

    def do_shutdown(self):
        """Cleanly close all window resources and database on application quit."""
        # Optional auto-backup on exit
        if self.config_manager and self.db:
            if self.config_manager.get_auto_backup_folder_enabled():
                folder = self.config_manager.get_auto_backup_folder()
                if folder and os.path.isdir(folder):
                    try:
                        date_suffix = time.strftime("%Y%m%d_%H%M%S")
                        is_enc = self.config_manager.get_auto_backup_encrypted()
                        pwd = self.config_manager.get_auto_backup_password()
                        if is_enc and pwd:
                            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                                tmp_path = tmp.name
                            self.db.backup_to_file(tmp_path)
                            target_file = os.path.join(folder, f"teddynotes_backup_{date_suffix}.db.gpg")
                            backup_encryption.encrypt_file(tmp_path, target_file, pwd)
                            try:
                                os.unlink(tmp_path)
                            except Exception:
                                pass
                        else:
                            target_file = os.path.join(folder, f"teddynotes_backup_{date_suffix}.db")
                            self.db.backup_to_file(target_file)
                        self.config_manager.set_last_local_backup(time.strftime("%Y-%m-%d %H:%M"))
                    except Exception as e:
                        print("Auto-backup to folder on exit failed:", e)

        for win in list(self.get_windows()):
            if hasattr(win, "_cleanup"):
                try:
                    win._cleanup()
                except Exception:
                    pass
        if hasattr(self, "db") and self.db:
            try:
                self.db.close()
            except Exception:
                pass
            self.db = None
        Gio.Application.do_shutdown(self)

    def _load_css(self):
        css_path = get_assets_path() / "css" / "style.css"
        if css_path.exists():
            provider = Gtk.CssProvider()
            try:
                provider.load_from_path(str(css_path))
                display = Gdk.Display.get_default()
                if display:
                    Gtk.StyleContext.add_provider_for_display(
                        display,
                        provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                    )
            except Exception as e:
                print("Error loading CSS:", e)

    def _setup_actions(self):
        def add_simple_action(name, callback, accels=None):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
            if accels:
                self.set_accels_for_action(f"app.{name}", accels)

        add_simple_action("new-window", self._on_new_window, ["<Control><Shift>n"])
        add_simple_action("about", self._on_about)
        add_simple_action("preferences", self._on_preferences, ["<Control>comma"])
        add_simple_action("shortcuts", self._on_shortcuts, ["<Control>question"])
        add_simple_action("quit", lambda _a, _p: self.quit(), ["<Control>q"])

    def _on_new_window(self, _action, _param):
        win = self.create_window()
        win.present()

    def _on_about(self, _action, _param):
        about = Adw.AboutDialog()
        about.set_application_name(APP_NAME)
        about.set_application_icon(APP_ID)
        about.set_version(VERSION)
        about.set_developer_name("Mohammed Asif Ali Rizvan")
        about.set_developers(["Mohammed Asif Ali Rizvan <fast.rizwaan@gmail.com>"])
        about.set_artists(["Mohammed Asif Ali Rizvan"])
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_comments("Iotas inspired rich text notes with dynamic WebKit Markdown rendering")
        about.set_website("https://github.com/fastrizwaan/TeddyNotes")
        about.set_issue_url("https://github.com/fastrizwaan/TeddyNotes/issues")

        parent = self.get_active_window()
        about.present(parent)

    def _on_preferences(self, _action, _param):
        parent = self.get_active_window()
        dialog = Adw.PreferencesDialog()
        dialog.set_title("Preferences")

        # ── Page 1: General ───────────────────────────────────────────────────
        page_general = Adw.PreferencesPage()
        page_general.set_title("General")
        page_general.set_icon_name("preferences-system-symbolic")

        # Appearance Group
        group_app = Adw.PreferencesGroup()
        group_app.set_title("Appearance")
        group_app.set_description("Customize how Teddy Notes looks and behaves")

        theme_row = Adw.ComboRow()
        theme_row.set_title("Color Scheme")
        theme_row.set_model(Gtk.StringList.new(["Follow System", "Light", "Dark"]))

        style_manager = Adw.StyleManager.get_default()
        cur_scheme = style_manager.get_color_scheme()
        if cur_scheme == Adw.ColorScheme.FORCE_LIGHT:
            theme_row.set_selected(1)
        elif cur_scheme == Adw.ColorScheme.FORCE_DARK:
            theme_row.set_selected(2)
        else:
            theme_row.set_selected(0)

        def on_theme_changed(row, _param):
            idx = row.get_selected()
            if idx == 1:
                style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
                if hasattr(self, "config_manager"):
                    self.config_manager.set_theme_mode("light")
            elif idx == 2:
                style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
                if hasattr(self, "config_manager"):
                    self.config_manager.set_theme_mode("dark")
            else:
                style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
                if hasattr(self, "config_manager"):
                    self.config_manager.set_theme_mode("follow")

        theme_row.connect("notify::selected", on_theme_changed)
        group_app.add(theme_row)

        # Editor Mode Row
        editor_mode_row = Adw.ComboRow()
        editor_mode_row.set_title("Editor View Mode")
        editor_mode_row.set_subtitle("Sidebar visibility while editing a note")
        editor_mode_row.set_model(Gtk.StringList.new([
            "Standard (Keep sidebar visible)",
            "Distraction-Free (Hide sidebar)"
        ]))
        cur_mode = self.config_manager.get_editor_mode() if hasattr(self, "config_manager") else "standard"
        editor_mode_row.set_selected(0 if cur_mode == "standard" else 1)

        def on_editor_mode_changed(row, _param):
            mode = "standard" if row.get_selected() == 0 else "distraction_free"
            if hasattr(self, "config_manager"):
                self.config_manager.set_editor_mode(mode)
            for win in self.get_windows():
                if hasattr(win, "apply_editor_mode"):
                    win.apply_editor_mode(mode)

        editor_mode_row.connect("notify::selected", on_editor_mode_changed)
        group_app.add(editor_mode_row)
        page_general.add(group_app)

        # Storage group
        group_storage = Adw.PreferencesGroup()
        group_storage.set_title("Storage")
        path_row = Adw.ActionRow()
        path_row.set_title("Database Location")
        if self.db:
            path_row.set_subtitle(str(self.db.db_path))
        group_storage.add(path_row)
        page_general.add(group_storage)

        # Private Notes Security group
        group_security = Adw.PreferencesGroup()
        group_security.set_title("Private Notes")
        group_security.set_description("Master password for locking notes and accessing private notes")

        private_pwd_row = Adw.ActionRow()
        private_pwd_row.set_title("Private Note Password")

        private_pwd_btn = Gtk.Button()
        private_pwd_btn.set_valign(Gtk.Align.CENTER)

        private_pwd_clear_btn = Gtk.Button()
        private_pwd_clear_btn.set_icon_name("edit-clear-symbolic")
        private_pwd_clear_btn.set_tooltip_text("Clear Private Note Password")
        private_pwd_clear_btn.add_css_class("flat")
        private_pwd_clear_btn.set_valign(Gtk.Align.CENTER)

        def update_private_pwd_ui():
            has_pwd = bool(self.db and self.db.has_private_password())
            private_pwd_row.set_subtitle("•••••••• (Password configured)" if has_pwd else "No password configured")
            private_pwd_btn.set_label("Change…" if has_pwd else "Set Password…")
            private_pwd_clear_btn.set_visible(has_pwd)

        update_private_pwd_ui()

        def on_private_pwd_btn_clicked(_btn):
            has_pwd = bool(self.db and self.db.has_private_password())
            dlg = Adw.AlertDialog.new(
                "Change Private Note Password" if has_pwd else "Set Private Note Password",
                "Enter your password to protect private notes."
            )
            dlg.add_response("cancel", "Cancel")
            dlg.add_response("save", "Save")
            dlg.set_default_response("save")
            dlg.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            box.set_margin_top(6)
            box.set_margin_bottom(6)

            grp = Adw.PreferencesGroup()
            curr_entry = None
            if has_pwd:
                curr_entry = Adw.PasswordEntryRow()
                curr_entry.set_title("Current Password")
                grp.add(curr_entry)

            new_entry = Adw.PasswordEntryRow()
            new_entry.set_title("New Password")
            grp.add(new_entry)

            confirm_entry = Adw.PasswordEntryRow()
            confirm_entry.set_title("Confirm Password")
            grp.add(confirm_entry)

            box.append(grp)
            dlg.set_extra_child(box)

            def on_dlg_res(_d, resp):
                if resp != "save":
                    return
                if has_pwd and curr_entry:
                    curr_val = curr_entry.get_text()
                    if not self.db.verify_private_password(curr_val):
                        err_d = Adw.AlertDialog.new("Incorrect Password", "The current password entered is incorrect.")
                        err_d.add_response("ok", "OK")
                        err_d.present(parent or dialog)
                        return

                new_val = new_entry.get_text()
                conf_val = confirm_entry.get_text()
                if not new_val.strip():
                    err_d = Adw.AlertDialog.new("Password Required", "Please enter a non-empty password.")
                    err_d.add_response("ok", "OK")
                    err_d.present(parent or dialog)
                    return
                if new_val != conf_val:
                    err_d = Adw.AlertDialog.new("Passwords Do Not Match", "The entered passwords do not match.")
                    err_d.add_response("ok", "OK")
                    err_d.present(parent or dialog)
                    return

                self.db.set_private_password(new_val)
                update_private_pwd_ui()
                if parent and hasattr(parent, "toast_overlay"):
                    parent.toast_overlay.add_toast(Adw.Toast.new("Private note password updated"))

            dlg.connect("response", on_dlg_res)
            dlg.present(parent or dialog)

        def on_private_pwd_clear_clicked(_btn):
            dlg = Adw.AlertDialog.new(
                "Remove Private Note Password?",
                "Enter your current password to remove private note password protection."
            )
            dlg.add_response("cancel", "Cancel")
            dlg.add_response("remove", "Remove")
            dlg.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            box.set_margin_top(6)
            box.set_margin_bottom(6)
            grp = Adw.PreferencesGroup()
            curr_entry = Adw.PasswordEntryRow()
            curr_entry.set_title("Current Password")
            grp.add(curr_entry)
            box.append(grp)
            dlg.set_extra_child(box)

            def on_clear_res(_d, resp):
                if resp != "remove":
                    return
                curr_val = curr_entry.get_text()
                if not self.db.verify_private_password(curr_val):
                    err_d = Adw.AlertDialog.new("Incorrect Password", "The current password entered is incorrect.")
                    err_d.add_response("ok", "OK")
                    err_d.present(parent or dialog)
                    return

                self.db.clear_private_password()
                update_private_pwd_ui()
                if parent and hasattr(parent, "toast_overlay"):
                    parent.toast_overlay.add_toast(Adw.Toast.new("Private note password removed"))

            dlg.connect("response", on_clear_res)
            dlg.present(parent or dialog)

        private_pwd_btn.connect("clicked", on_private_pwd_btn_clicked)
        private_pwd_clear_btn.connect("clicked", on_private_pwd_clear_clicked)
        private_pwd_row.add_suffix(private_pwd_btn)
        private_pwd_row.add_suffix(private_pwd_clear_btn)
        group_security.add(private_pwd_row)
        page_general.add(group_security)
        dialog.add(page_general)

        # ── Page 2: Typography ────────────────────────────────────────────────
        page_typo = Adw.PreferencesPage()
        page_typo.set_title("Typography")
        page_typo.set_icon_name("font-x-generic-symbolic")

        def notify_windows_typography():
            for win in self.get_windows():
                if hasattr(win, "editor"):
                    if hasattr(win.editor, "update_typography"):
                        win.editor.update_typography()
                    if hasattr(win.editor, "font_size_selector"):
                        win.editor.font_size_selector.refresh()

        def notify_windows_card_size(size_str: str):
            for win in self.get_windows():
                if hasattr(win, "apply_card_size"):
                    win.apply_card_size(size_str)

        # Group 1: Notes List & Cards
        group_cards = Adw.PreferencesGroup()
        group_cards.set_title("Notes List &amp; Cards")
        group_cards.set_description("Font size for note card titles, dates, and previews")

        card_size_row = Adw.ComboRow()
        if hasattr(card_size_row, "set_use_markup"):
            card_size_row.set_use_markup(False)
        card_size_row.set_title("Card & List Text Size")
        card_size_row.set_model(Gtk.StringList.new([
            "Small (85%)",
            "Normal (Default)",
            "Large (120%)",
            "Extra Large (140%)"
        ]))
        card_size_keys = ["small", "default", "large", "xlarge"]
        cur_card_size = self.config_manager.get_card_font_size() if hasattr(self, "config_manager") else "default"
        card_size_idx = card_size_keys.index(cur_card_size) if cur_card_size in card_size_keys else 1
        card_size_row.set_selected(card_size_idx)

        def on_card_size_changed(row, _param):
            idx = row.get_selected()
            if 0 <= idx < len(card_size_keys):
                selected = card_size_keys[idx]
                if hasattr(self, "config_manager"):
                    self.config_manager.set_card_font_size(selected)
                notify_windows_card_size(selected)

        card_size_row.connect("notify::selected", on_card_size_changed)
        group_cards.add(card_size_row)
        page_typo.add(group_cards)

        # Group 2: Note Content
        group_editor = Adw.PreferencesGroup()
        group_editor.set_title("Note Content")
        group_editor.set_description("Typeface and zoom level for note body, headings, code, and quotes")

        font_family_row = Adw.ComboRow()
        font_family_row.set_title("Font Family")
        font_family_row.set_subtitle("Typeface for note content and headings")
        font_family_row.set_model(Gtk.StringList.new([
            "System (Default)",
            "Sans-Serif",
            "Serif",
            "Monospace"
        ]))
        font_family_keys = ["system", "sans", "serif", "monospace"]
        cur_font_family = self.config_manager.get_font_family() if hasattr(self, "config_manager") else "system"
        font_family_idx = font_family_keys.index(cur_font_family) if cur_font_family in font_family_keys else 0
        font_family_row.set_selected(font_family_idx)

        def on_font_family_changed(row, _param):
            idx = row.get_selected()
            if 0 <= idx < len(font_family_keys):
                selected_family = font_family_keys[idx]
                if hasattr(self, "config_manager"):
                    self.config_manager.set_font_family(selected_family)
                notify_windows_typography()

        font_family_row.connect("notify::selected", on_font_family_changed)
        group_editor.add(font_family_row)

        editor_size_row = Adw.ComboRow()
        editor_size_row.set_title("Note Text Size")
        editor_size_row.set_subtitle("Zoom percentage for note content")
        editor_size_row.set_model(Gtk.StringList.new([
            "80%",
            "90%",
            "100% (Default)",
            "110%",
            "120%",
            "130%",
            "140%",
            "150%",
            "160%"
        ]))
        editor_percent_values = [80, 90, 100, 110, 120, 130, 140, 150, 160]
        cur_percent = self.config_manager.get_editor_zoom_percent() if hasattr(self, "config_manager") else 100
        editor_size_idx = editor_percent_values.index(cur_percent) if cur_percent in editor_percent_values else 2
        editor_size_row.set_selected(editor_size_idx)

        def on_editor_size_changed(row, _param):
            idx = row.get_selected()
            if 0 <= idx < len(editor_percent_values):
                selected_pct = editor_percent_values[idx]
                if hasattr(self, "config_manager"):
                    self.config_manager.set_editor_zoom_percent(selected_pct)
                notify_windows_typography()

        editor_size_row.connect("notify::selected", on_editor_size_changed)
        group_editor.add(editor_size_row)
        page_typo.add(group_editor)

        # Group 3: Reset to Defaults
        group_reset = Adw.PreferencesGroup()
        reset_row = Adw.ActionRow()
        reset_row.set_title("Reset to Defaults")
        reset_row.set_subtitle("Restore default font family, text sizes, and zoom")
        reset_btn = Gtk.Button(label="Reset to Defaults")
        reset_btn.add_css_class("suggested-action")
        reset_btn.set_valign(Gtk.Align.CENTER)

        def on_reset_typography(_b):
            if hasattr(self, "config_manager"):
                self.config_manager.reset_typography_defaults()
            card_size_row.set_selected(1)
            font_family_row.set_selected(0)
            editor_size_row.set_selected(2)
            notify_windows_card_size("default")
            notify_windows_typography()

        reset_btn.connect("clicked", on_reset_typography)
        reset_row.add_suffix(reset_btn)
        reset_row.set_activatable_widget(reset_btn)
        group_reset.add(reset_row)
        page_typo.add(group_reset)
        dialog.add(page_typo)

        # ── Page 3: Backup & Restore ─────────────────────────────────────────
        page_backup = Adw.PreferencesPage()
        page_backup.set_title("Backup & Restore")
        page_backup.set_icon_name("folder-download-symbolic")

        target_win = parent if isinstance(parent, Gtk.Window) else None

        # ── Group 1: Backup and Restore ──────────────────────────────────────
        group_manual = Adw.PreferencesGroup()
        group_manual.set_title("Backup and Restore")
        group_manual.set_description("Create or restore snapshots of your notes, categories, and attachments")

        # Row 1: Backup Database to File
        backup_row = Adw.ActionRow()
        backup_row.set_title("Backup Notes Database")
        last_bk = self.config_manager.get_last_local_backup() if self.config_manager else ""
        backup_row.set_subtitle(f"Last backup: {last_bk}" if last_bk else "Export an atomic snapshot (.db or password-protected .db.gpg)")

        backup_btn = Gtk.Button(label="Backup to File…")
        backup_btn.add_css_class("suggested-action")
        backup_btn.set_valign(Gtk.Align.CENTER)
        backup_row.add_suffix(backup_btn)
        backup_row.set_activatable_widget(backup_btn)
        group_manual.add(backup_row)

        # Row 2: Restore Notes Database
        restore_row = Adw.ActionRow()
        restore_row.set_title("Restore Notes Database")
        restore_row.set_subtitle("Restore notes from a backup file (.db or encrypted .db.gpg)")

        restore_btn = Gtk.Button(label="Restore from File…")
        restore_btn.set_valign(Gtk.Align.CENTER)
        restore_row.add_suffix(restore_btn)
        restore_row.set_activatable_widget(restore_btn)
        group_manual.add(restore_row)

        page_backup.add(group_manual)

        # ── Group 2: Automatic Backups ───────────────────────────────────────
        group_auto = Adw.PreferencesGroup()
        group_auto.set_title("Automatic Backups")
        group_auto.set_description("Automatically save a backup copy whenever Teddy Notes is closed")

        auto_backup_switch = Adw.SwitchRow()
        auto_backup_switch.set_title("Auto-Backup on Exit")
        auto_backup_switch.set_subtitle("Save a timestamped snapshot when closing Teddy Notes")
        auto_backup_switch.set_active(self.config_manager.get_auto_backup_folder_enabled() if self.config_manager else False)

        def on_auto_backup_toggled(row, _param):
            if self.config_manager:
                self.config_manager.set_auto_backup_folder_enabled(row.get_active())

        auto_backup_switch.connect("notify::active", on_auto_backup_toggled)
        group_auto.add(auto_backup_switch)

        folder_row = Adw.ActionRow()
        folder_row.set_title("Backup Destination Folder")
        cur_folder = self.config_manager.get_auto_backup_folder() if self.config_manager else ""
        folder_row.set_subtitle(cur_folder if cur_folder else "No folder selected (Click to choose a destination folder)")

        choose_folder_btn = Gtk.Button(label="Choose Folder…")
        choose_folder_btn.set_valign(Gtk.Align.CENTER)

        def on_choose_folder_clicked(_btn):
            fd = Gtk.FileDialog()
            fd.set_title("Select Backup Destination Folder")

            def on_folder_finish(fd, res):
                try:
                    target = fd.select_folder_finish(res)
                    if target:
                        folder_path = target.get_path()
                        if not folder_path:
                            uri = target.get_uri() or ""
                            if uri.startswith("file://"):
                                folder_path = urllib.parse.unquote(uri[7:])
                        if folder_path:
                            if self.config_manager:
                                self.config_manager.set_auto_backup_folder(folder_path)
                            folder_row.set_subtitle(folder_path)
                            if parent and hasattr(parent, "toast_overlay"):
                                parent.toast_overlay.add_toast(Adw.Toast.new(f"Backup folder set to {os.path.basename(folder_path)}"))
                except Exception as e:
                    print("Folder chooser cancelled or failed:", e)

            fd.select_folder(target_win, None, on_folder_finish)

        choose_folder_btn.connect("clicked", on_choose_folder_clicked)
        folder_row.add_suffix(choose_folder_btn)
        folder_row.set_activatable_widget(choose_folder_btn)
        group_auto.add(folder_row)

        # Encrypted Auto-Backup
        auto_enc_switch = Adw.SwitchRow()
        auto_enc_switch.set_title("Encrypt Auto-Backups with Password")
        auto_enc_switch.set_subtitle("Protect auto-backups with standalone GPG AES-256 encryption")
        auto_enc_switch.set_active(self.config_manager.get_auto_backup_encrypted() if self.config_manager else False)

        auto_pwd_row = Adw.ActionRow()
        auto_pwd_row.set_title("Auto-Backup Password")

        auto_pwd_btn = Gtk.Button()
        auto_pwd_btn.set_valign(Gtk.Align.CENTER)

        auto_pwd_clear_btn = Gtk.Button()
        auto_pwd_clear_btn.set_icon_name("edit-clear-symbolic")
        auto_pwd_clear_btn.set_tooltip_text("Clear Auto-Backup Password")
        auto_pwd_clear_btn.add_css_class("flat")
        auto_pwd_clear_btn.set_valign(Gtk.Align.CENTER)

        def update_auto_pwd_ui():
            cur_pwd = self.config_manager.get_auto_backup_password() if self.config_manager else ""
            has_pwd = bool(cur_pwd)
            auto_pwd_row.set_subtitle("•••••••• (Password configured)" if has_pwd else "No password configured")
            auto_pwd_btn.set_label("Change…" if has_pwd else "Set Password…")
            auto_pwd_clear_btn.set_visible(has_pwd)
            is_enc = auto_enc_switch.get_active()
            auto_pwd_row.set_sensitive(is_enc)
            auto_pwd_btn.set_sensitive(is_enc)
            auto_pwd_clear_btn.set_sensitive(is_enc)

        update_auto_pwd_ui()

        def on_auto_pwd_btn_clicked(_btn):
            cur_pwd = self.config_manager.get_auto_backup_password() if self.config_manager else ""
            has_pwd = bool(cur_pwd)
            dlg = Adw.AlertDialog.new(
                "Change Auto-Backup Password" if has_pwd else "Set Auto-Backup Password",
                "Enter a password to encrypt automated backups."
            )
            dlg.add_response("cancel", "Cancel")
            dlg.add_response("save", "Save")
            dlg.set_default_response("save")
            dlg.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            box.set_margin_top(6)
            box.set_margin_bottom(6)

            grp = Adw.PreferencesGroup()
            new_entry = Adw.PasswordEntryRow()
            new_entry.set_title("New Password")
            grp.add(new_entry)

            confirm_entry = Adw.PasswordEntryRow()
            confirm_entry.set_title("Confirm Password")
            grp.add(confirm_entry)

            box.append(grp)
            dlg.set_extra_child(box)

            def on_dlg_res(_d, resp):
                if resp != "save":
                    return
                new_val = new_entry.get_text()
                conf_val = confirm_entry.get_text()
                if not new_val.strip():
                    err_d = Adw.AlertDialog.new("Password Required", "Please enter a non-empty password.")
                    err_d.add_response("ok", "OK")
                    err_d.present(parent or dialog)
                    return
                if new_val != conf_val:
                    err_d = Adw.AlertDialog.new("Passwords Do Not Match", "The entered passwords do not match.")
                    err_d.add_response("ok", "OK")
                    err_d.present(parent or dialog)
                    return

                if self.config_manager:
                    self.config_manager.set_auto_backup_password(new_val)
                update_auto_pwd_ui()
                if parent and hasattr(parent, "toast_overlay"):
                    parent.toast_overlay.add_toast(Adw.Toast.new("Auto-backup password updated"))

            dlg.connect("response", on_dlg_res)
            dlg.present(parent or dialog)

        def on_auto_pwd_clear_clicked(_btn):
            if self.config_manager:
                self.config_manager.set_auto_backup_password("")
            update_auto_pwd_ui()
            if parent and hasattr(parent, "toast_overlay"):
                parent.toast_overlay.add_toast(Adw.Toast.new("Auto-backup password cleared"))

        def on_auto_enc_toggled(row, _param):
            is_active = row.get_active()
            if self.config_manager:
                self.config_manager.set_auto_backup_encrypted(is_active)
            update_auto_pwd_ui()

        auto_enc_switch.connect("notify::active", on_auto_enc_toggled)
        auto_pwd_btn.connect("clicked", on_auto_pwd_btn_clicked)
        auto_pwd_clear_btn.connect("clicked", on_auto_pwd_clear_clicked)
        auto_pwd_row.add_suffix(auto_pwd_btn)
        auto_pwd_row.add_suffix(auto_pwd_clear_btn)
        group_auto.add(auto_enc_switch)
        group_auto.add(auto_pwd_row)

        page_backup.add(group_auto)
        dialog.add(page_backup)

        # ── Backup Button Callback ───────────────────────────────────────────
        def on_backup_clicked(_btn):
            if not self.db:
                return

            dlg = Adw.AlertDialog.new(
                "Create Notes Backup",
                "Export a full snapshot of your notes, categories, and attachments."
            )
            dlg.add_response("cancel", "Cancel")
            dlg.add_response("continue", "Continue")
            dlg.set_default_response("continue")
            dlg.set_response_appearance("continue", Adw.ResponseAppearance.SUGGESTED)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            box.set_margin_top(6)
            box.set_margin_bottom(6)

            pwd_group = Adw.PreferencesGroup()

            exclude_switch = Adw.SwitchRow()
            exclude_switch.set_title("Exclude private notes and password")
            exclude_switch.set_subtitle("Omit locked private notes, attachments, and password hash")
            pwd_group.add(exclude_switch)

            enc_switch = Adw.SwitchRow()
            enc_switch.set_title("Password Protect Backup")
            enc_switch.set_subtitle("Encrypt backup file using GPG AES-256")
            pwd_group.add(enc_switch)

            pwd_entry = Adw.PasswordEntryRow()
            pwd_entry.set_title("Password")
            pwd_entry.set_visible(False)
            pwd_group.add(pwd_entry)

            pwd_confirm = Adw.PasswordEntryRow()
            pwd_confirm.set_title("Confirm Password")
            pwd_confirm.set_visible(False)
            pwd_group.add(pwd_confirm)

            def on_enc_switch_notify(sw, _param):
                active = sw.get_active()
                pwd_entry.set_visible(active)
                pwd_confirm.set_visible(active)

            enc_switch.connect("notify::active", on_enc_switch_notify)
            box.append(pwd_group)
            dlg.set_extra_child(box)

            def on_dlg_response(_d, response):
                if response != "continue":
                    return

                exclude_private = exclude_switch.get_active()
                is_encrypted = enc_switch.get_active()
                password = pwd_entry.get_text()
                confirm = pwd_confirm.get_text()

                if is_encrypted:
                    if not password:
                        err_d = Adw.AlertDialog.new("Password Required", "Please enter a password to protect the backup.")
                        err_d.add_response("ok", "OK")
                        err_d.present(parent or dialog)
                        return
                    if password != confirm:
                        err_d = Adw.AlertDialog.new("Passwords Do Not Match", "The entered passwords do not match. Please try again.")
                        err_d.add_response("ok", "OK")
                        err_d.present(parent or dialog)
                        return

                file_dialog = Gtk.FileDialog()
                file_dialog.set_title("Save Backup Database")
                date_str = time.strftime("%Y-%m-%d")
                ext = ".db.gpg" if is_encrypted else ".db"
                file_dialog.set_initial_name(f"teddynotes_backup_{date_str}{ext}")

                filters = Gio.ListStore.new(Gtk.FileFilter)
                if is_encrypted:
                    f_enc = Gtk.FileFilter()
                    f_enc.set_name("Encrypted Teddy Notes Backup (*.db.gpg, *.gpg)")
                    f_enc.add_pattern("*.db.gpg")
                    f_enc.add_pattern("*.gpg")
                    filters.append(f_enc)
                    file_dialog.set_default_filter(f_enc)
                else:
                    f_db = Gtk.FileFilter()
                    f_db.set_name("Teddy Notes Backup (*.db)")
                    f_db.add_pattern("*.db")
                    filters.append(f_db)
                    file_dialog.set_default_filter(f_db)

                f_all = Gtk.FileFilter()
                f_all.set_name("All Files")
                f_all.add_pattern("*")
                filters.append(f_all)
                file_dialog.set_filters(filters)

                def on_save_finish(fd, res):
                    try:
                        target = fd.save_finish(res)
                        if target:
                            target_path = target.get_path()
                            if not target_path:
                                uri = target.get_uri() or ""
                                if uri.startswith("file://"):
                                    target_path = urllib.parse.unquote(uri[7:])
                            if target_path:
                                def save_worker():
                                    try:
                                        if is_encrypted:
                                            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                                                tmp_path = tmp.name
                                            self.db.backup_to_file(tmp_path, exclude_private=exclude_private)
                                            backup_encryption.encrypt_file(tmp_path, target_path, password)
                                            try:
                                                os.unlink(tmp_path)
                                            except Exception:
                                                pass
                                        else:
                                            self.db.backup_to_file(target_path, exclude_private=exclude_private)

                                        now_str = time.strftime("%Y-%m-%d %H:%M")
                                        if self.config_manager:
                                            self.config_manager.set_last_local_backup(now_str)

                                        def on_save_success():
                                            backup_row.set_subtitle(f"Last backup: {now_str}")
                                            if parent and hasattr(parent, "toast_overlay"):
                                                notes_info = []
                                                if exclude_private:
                                                    notes_info.append("private notes excluded")
                                                if is_encrypted:
                                                    notes_info.append("encrypted")
                                                suffix_str = f" ({', '.join(notes_info)})" if notes_info else ""
                                                parent.toast_overlay.add_toast(Adw.Toast.new(f"Backup saved to {os.path.basename(target_path)}{suffix_str}"))
                                        GLib.idle_add(on_save_success)
                                    except Exception as e:
                                        def on_save_err(err_msg):
                                            err_dlg = Adw.AlertDialog.new("Backup Failed", err_msg)
                                            err_dlg.add_response("ok", "OK")
                                            err_dlg.present(parent or dialog)
                                        GLib.idle_add(on_save_err, str(e))

                                threading.Thread(target=save_worker, daemon=True).start()
                    except Exception as e:
                        print("Save dialog error or cancelled:", e)

                file_dialog.save(target_win, None, on_save_finish)

            dlg.connect("response", on_dlg_response)
            dlg.present(parent or dialog)

        backup_btn.connect("clicked", on_backup_clicked)

        # ── Restore Button Callback ──────────────────────────────────────────
        def on_restore_clicked(_btn):
            if not self.db:
                return

            file_dialog = Gtk.FileDialog()
            file_dialog.set_title("Select Backup File to Restore")

            filter_any_backup = Gtk.FileFilter()
            filter_any_backup.set_name("Teddy Notes Backups (*.db, *.db.gpg, *.gpg)")
            filter_any_backup.add_pattern("*.db")
            filter_any_backup.add_pattern("*.db.gpg")
            filter_any_backup.add_pattern("*.gpg")

            filter_all = Gtk.FileFilter()
            filter_all.set_name("All Files")
            filter_all.add_pattern("*")

            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(filter_any_backup)
            filters.append(filter_all)
            file_dialog.set_filters(filters)
            file_dialog.set_default_filter(filter_any_backup)

            def on_open_finish(fd, res):
                try:
                    target = fd.open_finish(res)
                    if not target:
                        return
                    target_path = target.get_path()
                    if not target_path:
                        uri = target.get_uri() or ""
                        if uri.startswith("file://"):
                            target_path = urllib.parse.unquote(uri[7:])
                    if not target_path or not os.path.isfile(target_path):
                        return

                    is_enc = backup_encryption.is_encrypted_file(target_path)
                    basename = os.path.basename(target_path)

                    if is_enc:
                        pwd_dlg = Adw.AlertDialog.new(
                            "Encrypted Backup",
                            f"'{basename}' is protected with a password. Enter the password to decrypt and restore:"
                        )
                        pwd_dlg.add_response("cancel", "Cancel")
                        pwd_dlg.add_response("restore", "Decrypt & Restore")
                        pwd_dlg.set_response_appearance("restore", Adw.ResponseAppearance.DESTRUCTIVE)
                        pwd_dlg.set_default_response("restore")

                        restore_pwd_group = Adw.PreferencesGroup()
                        restore_pwd_entry = Adw.PasswordEntryRow()
                        restore_pwd_entry.set_title("Backup Password")
                        restore_pwd_group.add(restore_pwd_entry)
                        pwd_dlg.set_extra_child(restore_pwd_group)

                        def on_pwd_response(_d, response):
                            if response != "restore":
                                return
                            pwd = restore_pwd_entry.get_text()
                            if not pwd:
                                err_d = Adw.AlertDialog.new("Password Required", "Please enter the backup password.")
                                err_d.add_response("ok", "OK")
                                err_d.present(parent or dialog)
                                return

                            def restore_enc_worker():
                                tmp_dec = None
                                try:
                                    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                                        tmp_dec = tmp.name
                                    backup_encryption.decrypt_file(target_path, tmp_dec, pwd)
                                    self.db.restore_from_file(tmp_dec)
                                    def on_success():
                                        for win in self.get_windows():
                                            if hasattr(win, "index_view"):
                                                win.index_view._private_unlocked = False
                                                win.index_view.refresh(update_sidebar=True)
                                        if parent and hasattr(parent, "toast_overlay"):
                                            parent.toast_overlay.add_toast(Adw.Toast.new("Notes successfully restored from encrypted backup!"))
                                    GLib.idle_add(on_success)
                                except ValueError as ve:
                                    def on_bad_pwd(msg):
                                        err_dlg = Adw.AlertDialog.new("Decryption Failed", str(msg))
                                        err_dlg.add_response("ok", "OK")
                                        err_dlg.present(parent or dialog)
                                    GLib.idle_add(on_bad_pwd, str(ve))
                                except Exception as e:
                                    def on_other_err(msg):
                                        err_dlg = Adw.AlertDialog.new("Restore Failed", str(msg))
                                        err_dlg.add_response("ok", "OK")
                                        err_dlg.present(parent or dialog)
                                    GLib.idle_add(on_other_err, str(e))
                                finally:
                                    if tmp_dec:
                                        try:
                                            os.unlink(tmp_dec)
                                        except Exception:
                                            pass

                            threading.Thread(target=restore_enc_worker, daemon=True).start()

                        pwd_dlg.connect("response", on_pwd_response)
                        pwd_dlg.present(parent or dialog)

                    else:
                        confirm_dlg = Adw.AlertDialog.new(
                            "Restore Notes from Backup?",
                            f"Restoring from '{basename}' will replace your current notes with this snapshot. Are you sure you want to proceed?"
                        )
                        confirm_dlg.add_response("cancel", "Cancel")
                        confirm_dlg.add_response("restore", "Restore Backup")
                        confirm_dlg.set_response_appearance("restore", Adw.ResponseAppearance.DESTRUCTIVE)
                        confirm_dlg.set_default_response("cancel")

                        def on_confirm_response(_d, response):
                            if response != "restore":
                                return

                            def restore_worker():
                                try:
                                    self.db.restore_from_file(target_path)
                                    def on_success():
                                        for win in self.get_windows():
                                            if hasattr(win, "index_view"):
                                                win.index_view._private_unlocked = False
                                                win.index_view.refresh(update_sidebar=True)
                                        if parent and hasattr(parent, "toast_overlay"):
                                            parent.toast_overlay.add_toast(Adw.Toast.new("Notes successfully restored from backup!"))
                                    GLib.idle_add(on_success)
                                except Exception as e:
                                    def on_err(err_msg):
                                        err_dlg = Adw.AlertDialog.new("Restore Failed", err_msg)
                                        err_dlg.add_response("ok", "OK")
                                        err_dlg.present(parent or dialog)
                                    GLib.idle_add(on_err, str(e))

                            threading.Thread(target=restore_worker, daemon=True).start()

                        confirm_dlg.connect("response", on_confirm_response)
                        confirm_dlg.present(parent or dialog)

                except Exception as e:
                    print("Restore selection cancelled or failed:", e)

            file_dialog.open(target_win, None, on_open_finish)

        restore_btn.connect("clicked", on_restore_clicked)

        dialog.present(parent)

    def _on_shortcuts(self, _action, _param):
        parent = self.get_active_window()
        builder = Gtk.Builder()

        shortcuts_xml = """<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <object class="GtkShortcutsWindow" id="shortcuts_window">
    <property name="modal">True</property>
    <child>
      <object class="GtkShortcutsSection">
        <property name="visible">True</property>
        <property name="section-name">shortcuts</property>
        <child>
          <object class="GtkShortcutsGroup">
            <property name="visible">True</property>
            <property name="title">General</property>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;&lt;Shift&gt;n</property>
                <property name="title">New window</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;n</property>
                <property name="title">Create new note</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;o</property>
                <property name="title">Open note from file</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;p</property>
                <property name="title">Print note</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;f</property>
                <property name="title">Search notes</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;backslash</property>
                <property name="title">Toggle sidebar folders</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;&lt;Shift&gt;d</property>
                <property name="title">Toggle dark / light theme</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">Escape</property>
                <property name="title">Go back to notes list</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;q</property>
                <property name="title">Quit application</property>
              </object>
            </child>
          </object>
        </child>
        <child>
          <object class="GtkShortcutsGroup">
            <property name="visible">True</property>
            <property name="title">Editor Formatting</property>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;e</property>
                <property name="title">Edit note / Toggle read-only mode</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;b</property>
                <property name="title">Bold text</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;i</property>
                <property name="title">Italic text</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;z</property>
                <property name="title">Undo</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;y</property>
                <property name="title">Redo</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;plus</property>
                <property name="title">Zoom in / Increase font</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;minus</property>
                <property name="title">Zoom out / Decrease font</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">&lt;Primary&gt;0</property>
                <property name="title">Reset font size</property>
              </object>
            </child>
            <child>
              <object class="GtkShortcutsShortcut">
                <property name="visible">True</property>
                <property name="accelerator">Tab</property>
                <property name="title">Next table cell or indent</property>
              </object>
            </child>
          </object>
        </child>
      </object>
    </child>
  </object>
</interface>
"""
        builder.add_from_string(shortcuts_xml)
        shortcuts_win = builder.get_object("shortcuts_window")
        shortcuts_win.set_transient_for(parent)
        shortcuts_win.present()

StiloApplication = TeddyApplication
