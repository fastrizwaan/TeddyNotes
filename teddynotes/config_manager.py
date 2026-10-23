# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional, Tuple
from gi.repository import Gio, GLib
from teddynotes.const import APP_ID

class ConfigManager:
    """Manages application settings and session memory."""

    _instance: Optional["ConfigManager"] = None

    def __init__(self, db=None):
        self.db = db
        self.settings: Optional[Gio.Settings] = None

        # Try loading Gio.Settings if schema is installed
        try:
            source = Gio.SettingsSchemaSource.get_default()
            if source and source.lookup(APP_ID, True):
                self.settings = Gio.Settings.new(APP_ID)
        except Exception:
            self.settings = None

    @classmethod
    def get_default(cls, db=None) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = ConfigManager(db)
        elif db is not None:
            cls._instance.db = db
        return cls._instance

    def get_window_size(self) -> Tuple[int, int]:
        if self.settings:
            try:
                val = self.settings.get_value("window-size")
                if val:
                    return val.unpack()
            except Exception:
                pass
        if self.db:
            raw = self.db.get_setting("window_size", "920,680")
            try:
                w, h = map(int, raw.split(","))
                return w, h
            except Exception:
                pass
        return 920, 680

    def set_window_size(self, width: int, height: int):
        if self.settings:
            try:
                self.settings.set_value("window-size", GLib.Variant("(ii)", (width, height)))
            except Exception:
                pass
        if self.db:
            self.db.set_setting("window_size", f"{width},{height}")

    def get_window_maximized(self) -> bool:
        if self.settings:
            try:
                return self.settings.get_boolean("window-maximized")
            except Exception:
                pass
        if self.db:
            return self.db.get_setting("window_maximized", "false") == "true"
        return False

    def set_window_maximized(self, maximized: bool):
        if self.settings:
            try:
                self.settings.set_boolean("window-maximized", maximized)
            except Exception:
                pass
        if self.db:
            self.db.set_setting("window_maximized", "true" if maximized else "false")

    def get_last_opened_note_id(self) -> str:
        if self.db:
            return self.db.get_setting("last_opened_note_id", "")
        return ""

    def set_last_opened_note_id(self, note_id: str):
        if self.db:
            self.db.set_setting("last_opened_note_id", note_id)

    def get_last_category(self) -> str:
        if self.db:
            return self.db.get_setting("last_category", "all")
        return "all"

    def set_last_category(self, cat: str):
        if self.db:
            self.db.set_setting("last_category", cat)

    def get_theme_mode(self) -> str:
        """Return 'follow', 'light', or 'dark'."""
        if self.db:
            mode = self.db.get_setting("theme_mode", "follow")
            if mode == "system":
                return "follow"
            return mode
        return "follow"

    def set_theme_mode(self, mode: str):
        if mode == "system":
            mode = "follow"
        if self.db:
            self.db.set_setting("theme_mode", mode)

    def get_font_size(self) -> int:
        """Return font size in pt (default 16)."""
        if self.db:
            try:
                return int(self.db.get_setting("font_size", "16"))
            except Exception:
                pass
        return 16

    def set_font_size(self, size: int):
        if self.db:
            self.db.set_setting("font_size", str(size))
            if size <= 14:
                self.db.set_setting("editor_font_size", "small")
            elif size <= 17:
                self.db.set_setting("editor_font_size", "default")
            elif size <= 20:
                self.db.set_setting("editor_font_size", "large")
            else:
                self.db.set_setting("editor_font_size", "xlarge")

    def get_view_mode(self) -> str:
        """Return 'list' or 'grid'."""
        if self.settings:
            try:
                mode = self.settings.get_string("view-mode")
                if mode in ("list", "grid"):
                    return mode
            except Exception:
                pass
        if self.db:
            mode = self.db.get_setting("view_mode", "list")
            if mode in ("list", "grid"):
                return mode
        return "list"

    def set_view_mode(self, mode: str):
        if mode not in ("list", "grid"):
            mode = "list"
        if self.settings:
            try:
                self.settings.set_string("view-mode", mode)
            except Exception:
                pass
        if self.db:
            self.db.set_setting("view_mode", mode)

    def get_collapsed_categories(self) -> set:
        """Return set of collapsed category full names."""
        if self.db:
            raw = self.db.get_setting("collapsed_categories", "")
            if raw:
                try:
                    import json
                    return set(json.loads(raw))
                except Exception:
                    pass
        return set()

    def set_collapsed_categories(self, collapsed: set):
        if self.db:
            import json
            self.db.set_setting("collapsed_categories", json.dumps(sorted(list(collapsed))))

    def get_categories_expanded(self) -> bool:
        """Return whether categories section in sidebar is expanded (default True)."""
        if self.db:
            return self.db.get_setting("categories_expanded", "true") == "true"
        return True

    def set_categories_expanded(self, expanded: bool):
        if self.db:
            self.db.set_setting("categories_expanded", "true" if expanded else "false")

    def get_tags_expanded(self) -> bool:
        """Return whether tags section in sidebar is expanded (default True)."""
        if self.db:
            return self.db.get_setting("tags_expanded", "true") == "true"
        return True

    def set_tags_expanded(self, expanded: bool):
        if self.db:
            self.db.set_setting("tags_expanded", "true" if expanded else "false")

    def get_toolbar_pinned(self) -> bool:
        """Return whether formatting toolbar is pinned."""
        if self.db:
            return self.db.get_setting("toolbar_pinned", "false") == "true"
        return False

    def set_toolbar_pinned(self, pinned: bool):
        if self.db:
            self.db.set_setting("toolbar_pinned", "true" if pinned else "false")

    def get_multi_column_mode(self) -> bool:
        """Return whether the editor uses responsive columns (enabled by default)."""
        if self.db:
            return self.db.get_setting("multi_column_mode", "true") == "true"
        return True

    def set_multi_column_mode(self, enabled: bool):
        if self.db:
            self.db.set_setting("multi_column_mode", "true" if enabled else "false")

    def get_centered_single_column_mode(self) -> bool:
        """Return whether the editor uses the centered single-column layout."""
        if self.db:
            return self.db.get_setting("centered_single_column_mode", "true") == "true"
        return False

    def set_centered_single_column_mode(self, enabled: bool):
        if self.db:
            self.db.set_setting("centered_single_column_mode", "true" if enabled else "false")

    def get_sidebar_width(self) -> int:
        """Return sidebar width in pixels (default 260, clamped 200..500)."""
        if self.db:
            try:
                val = int(self.db.get_setting("sidebar_width", "260"))
                return max(200, min(val, 500))
            except Exception:
                pass
        return 260

    def set_sidebar_width(self, width: int):
        clamped = max(200, min(int(width), 500))
        if self.db:
            self.db.set_setting("sidebar_width", str(clamped))

    def get_editor_mode(self) -> str:
        """Return 'standard' (default, keep sidebar) or 'distraction_free' (hide sidebar)."""
        if self.db:
            mode = self.db.get_setting("editor_mode", "standard")
            if mode in ("standard", "distraction_free"):
                return mode
        return "standard"

    def set_editor_mode(self, mode: str):
        if mode not in ("standard", "distraction_free"):
            mode = "standard"
        if self.db:
            self.db.set_setting("editor_mode", mode)

    def get_card_font_size(self) -> str:
        """Return 'small', 'default', 'large', or 'xlarge'."""
        if self.db:
            size = self.db.get_setting("card_font_size", "default")
            if size in ("small", "default", "large", "xlarge"):
                return size
        return "default"

    def set_card_font_size(self, size: str):
        if size not in ("small", "default", "large", "xlarge"):
            size = "default"
        if self.db:
            self.db.set_setting("card_font_size", size)

    EDITOR_ZOOM_MAP = {
        "small": 0.85,
        "default": 1.0,
        "large": 1.20,
        "xlarge": 1.40,
    }

    def get_editor_zoom_percent(self) -> int:
        """Return note editor zoom percentage (80..160, default 100)."""
        if self.db:
            try:
                raw = self.db.get_setting("editor_zoom_percent", "")
                if raw:
                    val = int(raw)
                    return max(80, min(val, 160))
            except Exception:
                pass
            size = self.db.get_setting("editor_font_size", "")
            if size == "small":
                return 80
            elif size == "large":
                return 120
            elif size == "xlarge":
                return 140
        return 100

    def set_editor_zoom_percent(self, percent: int):
        clamped = max(80, min(int(percent), 160))
        if self.db:
            self.db.set_setting("editor_zoom_percent", str(clamped))
            zoom = clamped / 100.0
            self.db.set_setting("font_size", str(round(16 * zoom)))
            if clamped <= 85:
                self.db.set_setting("editor_font_size", "small")
            elif clamped >= 135:
                self.db.set_setting("editor_font_size", "xlarge")
            elif clamped >= 115:
                self.db.set_setting("editor_font_size", "large")
            else:
                self.db.set_setting("editor_font_size", "default")

    def get_editor_font_size(self) -> str:
        """Return note editor text size preset: 'small', 'default', 'large', 'xlarge'."""
        pct = self.get_editor_zoom_percent()
        if pct <= 85:
            return "small"
        elif pct >= 135:
            return "xlarge"
        elif pct >= 115:
            return "large"
        return "default"

    def set_editor_font_size(self, size: str):
        pct_map = {"small": 80, "default": 100, "large": 120, "xlarge": 140}
        pct = pct_map.get(size, 100)
        self.set_editor_zoom_percent(pct)

    def get_editor_zoom_level(self) -> float:
        """Return zoom multiplier (e.g. 1.0 for 100%, 0.8 for 80%, 1.2 for 120%)."""
        return self.get_editor_zoom_percent() / 100.0

    def get_heading_scale(self) -> str:
        """Return heading scale: 'compact', 'normal', 'large', 'xlarge'."""
        if self.db:
            scale = self.db.get_setting("heading_scale", "normal")
            if scale in ("compact", "normal", "large", "xlarge"):
                return scale
        return "normal"

    def set_heading_scale(self, scale: str):
        if scale not in ("compact", "normal", "large", "xlarge"):
            scale = "normal"
        if self.db:
            self.db.set_setting("heading_scale", scale)

    def get_code_font_size(self) -> int:
        """Return monospace code font size in px (default 14, range 10..24)."""
        if self.db:
            try:
                val = int(self.db.get_setting("code_font_size", "14"))
                return max(10, min(val, 24))
            except Exception:
                pass
        return 14

    def set_code_font_size(self, size: int):
        clamped = max(10, min(int(size), 24))
        if self.db:
            self.db.set_setting("code_font_size", str(clamped))

    def get_quote_font_size(self) -> int:
        """Return quote font size in pt (default 16, range 10..24)."""
        if self.db:
            try:
                val = int(self.db.get_setting("quote_font_size", "16"))
                return max(10, min(val, 24))
            except Exception:
                pass
        return 16

    def set_quote_font_size(self, size: int):
        clamped = max(10, min(int(size), 24))
        if self.db:
            self.db.set_setting("quote_font_size", str(clamped))

    FONT_STACKS = {
        "system": '-apple-system, BlinkMacSystemFont, "Cantarell", "Inter", "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        "sans": '"Inter", "Cantarell", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        "serif": '"Charter", "Georgia", "Cambria", "Times New Roman", "Source Serif Pro", serif',
        "monospace": '"JetBrains Mono", "Fira Code", "Source Code Pro", SFMono-Regular, Menlo, Monaco, Consolas, monospace',
    }

    def get_font_family(self) -> str:
        """Return font family key: 'system', 'sans', 'serif', 'monospace' (default 'system')."""
        if self.db:
            family = self.db.get_setting("font_family", "system")
            if family in ("sans-serif", "sans_serif"):
                return "sans"
            if family in self.FONT_STACKS:
                return family
        return "system"

    def set_font_family(self, family: str):
        if family in ("sans-serif", "sans_serif"):
            family = "sans"
        if family not in self.FONT_STACKS:
            family = "system"
        if self.db:
            self.db.set_setting("font_family", family)

    def get_font_family_stack(self, family: Optional[str] = None) -> str:
        if family is None:
            family = self.get_font_family()
        elif family in ("sans-serif", "sans_serif"):
            family = "sans"
        return self.FONT_STACKS.get(family, self.FONT_STACKS["system"])

    def reset_typography_defaults(self):
        """Reset all typography settings to their default values."""
        self.set_card_font_size("default")
        self.set_font_family("system")
        self.set_editor_zoom_percent(100)
        self.set_heading_scale("normal")
        self.set_code_font_size(14)
        self.set_quote_font_size(16)

    # ── Database Backup Settings ─────────────────────────────────────────

    def get_auto_backup_folder(self) -> str:
        if self.db:
            return self.db.get_setting("auto_backup_folder", "")
        return ""

    def set_auto_backup_folder(self, folder_path: str):
        if self.db:
            self.db.set_setting("auto_backup_folder", folder_path.strip())

    def get_auto_backup_folder_enabled(self) -> bool:
        if self.db:
            return self.db.get_setting("auto_backup_folder_enabled", "false") == "true"
        return False

    def set_auto_backup_folder_enabled(self, enabled: bool):
        if self.db:
            self.db.set_setting("auto_backup_folder_enabled", "true" if enabled else "false")

    def get_auto_backup_encrypted(self) -> bool:
        if self.db:
            return self.db.get_setting("auto_backup_encrypted", "false") == "true"
        return False

    def set_auto_backup_encrypted(self, enabled: bool):
        if self.db:
            self.db.set_setting("auto_backup_encrypted", "true" if enabled else "false")

    def get_auto_backup_password(self) -> str:
        if self.db:
            return self.db.get_setting("auto_backup_password", "")
        return ""

    def set_auto_backup_password(self, password: str):
        if self.db:
            self.db.set_setting("auto_backup_password", password)

    def get_last_local_backup(self) -> str:
        if self.db:
            return self.db.get_setting("last_local_backup_time", "")
        return ""

    def set_last_local_backup(self, timestamp_str: str):
        if self.db:
            self.db.set_setting("last_local_backup_time", timestamp_str)

    # ── Page Setup Settings ──────────────────────────────────────────────

    def get_page_setup_paper(self) -> str:
        if self.db:
            val = self.db.get_setting("page_setup_paper", "iso_a4")
            if val in ("A4", "iso_a4"):
                return "iso_a4"
            elif val in ("US Letter", "Letter", "na_letter"):
                return "na_letter"
            elif val in ("Legal", "na_legal"):
                return "na_legal"
            elif val in ("A3", "iso_a3"):
                return "iso_a3"
            elif val in ("A5", "iso_a5"):
                return "iso_a5"
            return val
        return "iso_a4"

    def set_page_setup_paper(self, paper: str):
        if self.db:
            self.db.set_setting("page_setup_paper", paper)

    def get_page_setup_orientation(self) -> str:
        if self.db:
            return self.db.get_setting("page_setup_orientation", "portrait")
        return "portrait"

    def set_page_setup_orientation(self, orientation: str):
        if self.db:
            self.db.set_setting("page_setup_orientation", orientation)

    def get_page_setup_margins_points(self) -> Tuple[float, float, float, float]:
        """Return (top, right, bottom, left) margins in points."""
        if self.db:
            raw = self.db.get_setting("page_setup_margins", "72.0,72.0,72.0,72.0")
            try:
                parts = [float(x.strip()) for x in raw.split(",")]
                if len(parts) == 4:
                    return (parts[0], parts[1], parts[2], parts[3])
            except Exception:
                pass
        return (72.0, 72.0, 72.0, 72.0)

    def set_page_setup_margins_points(self, top: float, right: float, bottom: float, left: float):
        if self.db:
            self.db.set_setting("page_setup_margins", f"{top:.2f},{right:.2f},{bottom:.2f},{left:.2f}")

    def get_page_setup_unit(self) -> str:
        if self.db:
            return self.db.get_setting("page_setup_unit", "in")
        return "in"

    def set_page_setup_unit(self, unit: str):
        if self.db:
            self.db.set_setting("page_setup_unit", unit)

    def get_page_setup(self):
        """Create and return a Gtk.PageSetup initialized from stored configuration."""
        import gi
        gi.require_version('Gtk', '4.0')
        from gi.repository import Gtk
        page_setup = Gtk.PageSetup.new()
        paper_name = self.get_page_setup_paper()
        paper_size = Gtk.PaperSize.new(paper_name)
        page_setup.set_paper_size(paper_size)
        orient = Gtk.PageOrientation.LANDSCAPE if self.get_page_setup_orientation() == "landscape" else Gtk.PageOrientation.PORTRAIT
        page_setup.set_orientation(orient)
        top, right, bottom, left = self.get_page_setup_margins_points()
        page_setup.set_top_margin(top, Gtk.Unit.POINTS)
        page_setup.set_right_margin(right, Gtk.Unit.POINTS)
        page_setup.set_bottom_margin(bottom, Gtk.Unit.POINTS)
        page_setup.set_left_margin(left, Gtk.Unit.POINTS)
        return page_setup

    def set_page_setup(self, page_setup, unit: str = "in"):
        """Save a Gtk.PageSetup configuration."""
        if not page_setup:
            return
        import gi
        gi.require_version('Gtk', '4.0')
        from gi.repository import Gtk
        paper_size = page_setup.get_paper_size()
        if paper_size:
            self.set_page_setup_paper(paper_size.get_name())
        orient = "landscape" if page_setup.get_orientation() == Gtk.PageOrientation.LANDSCAPE else "portrait"
        self.set_page_setup_orientation(orient)
        top = page_setup.get_top_margin(Gtk.Unit.POINTS)
        right = page_setup.get_right_margin(Gtk.Unit.POINTS)
        bottom = page_setup.get_bottom_margin(Gtk.Unit.POINTS)
        left = page_setup.get_left_margin(Gtk.Unit.POINTS)
        self.set_page_setup_margins_points(top, right, bottom, left)
        self.set_page_setup_unit(unit)
