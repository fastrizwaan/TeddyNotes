# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional, Callable
from gi.repository import Adw, Gdk, Gtk, GObject
from teddynotes.config_manager import ConfigManager


_THEME_SELECTOR_CSS = """
.themeselector { margin: 6px 9px; }
button.theme-selector,
button.theme-selector:hover,
button.theme-selector:active,
button.theme-selector:checked {
    min-width: 44px;
    min-height: 44px;
    padding: 0;
    border: none;
    border-radius: 9999px;
    background-clip: padding-box;
    box-shadow: inset 0 0 0 1px alpha(currentColor, 0.25);
}
button.theme-selector:checked {
    box-shadow: inset 0 0 0 2px @accent_bg_color;
}
button.theme-selector.follow,
button.theme-selector.follow:hover,
button.theme-selector.follow:active,
button.theme-selector.follow:checked {
    background-color: transparent;
    background-image: linear-gradient(to bottom right, #ffffff 49.99%, #202020 50.01%);
}
button.theme-selector.light,
button.theme-selector.light:hover,
button.theme-selector.light:active,
button.theme-selector.light:checked {
    background-color: #ffffff;
    background-image: none;
}
button.theme-selector.dark,
button.theme-selector.dark:hover,
button.theme-selector.dark:active,
button.theme-selector.dark:checked {
    background-color: #202020;
    background-image: none;
}
button.theme-selector:not(:checked) image.theme-check {
    opacity: 0;
}
button.theme-selector image.theme-check {
    color: @accent_fg_color;
    background-color: @accent_bg_color;
    border-radius: 9999px;
    padding: 3px;
    -gtk-icon-size: 12px;
}
"""

_css_loaded = False


def _ensure_css():
    """Register the selector's own CSS once so it doesn't depend on style.css."""
    global _css_loaded
    if _css_loaded:
        return
    display = Gdk.Display.get_default()
    if display is None:
        return
    provider = Gtk.CssProvider()
    if hasattr(provider, "load_from_string"):
        provider.load_from_string(_THEME_SELECTOR_CSS)
    else:
        provider.load_from_data(_THEME_SELECTOR_CSS.encode("utf-8"))
    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    _css_loaded = True


class ThemeSelector(Gtk.Box):
    """Circular 3-option theme selector (Follow System, Light, Dark) matching Iotas."""

    __gtype_name__ = "ThemeSelector"

    def __init__(self, config_manager: Optional[ConfigManager] = None, on_theme_changed: Optional[Callable[[bool], None]] = None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        _ensure_css()
        self.add_css_class("themeselector")
        self.set_hexpand(True)

        self.config_manager = config_manager or ConfigManager.get_default()
        self.on_theme_changed = on_theme_changed
        self._updating = False

        inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        inner_box.set_hexpand(True)
        inner_box.set_homogeneous(True)
        self.append(inner_box)

        # 1. Follow System Style button
        self._follow = Gtk.ToggleButton()
        self._follow.set_tooltip_text("Follow System Style")
        self._follow.set_halign(Gtk.Align.CENTER)
        self._follow.set_valign(Gtk.Align.CENTER)
        self._follow.set_focus_on_click(False)
        self._follow.add_css_class("theme-selector")
        self._follow.add_css_class("follow")
        self._follow_check = Gtk.Image.new_from_icon_name("object-select-symbolic")
        self._follow_check.add_css_class("theme-check")
        self._follow_check.set_halign(Gtk.Align.END)
        self._follow_check.set_valign(Gtk.Align.END)
        self._follow_check.set_margin_end(2)
        self._follow_check.set_margin_bottom(2)
        self._follow.set_child(self._follow_check)
        inner_box.append(self._follow)

        # 2. Light Style button
        self._light = Gtk.ToggleButton()
        self._light.set_tooltip_text("Light Style")
        self._light.set_group(self._follow)
        self._light.set_halign(Gtk.Align.CENTER)
        self._light.set_valign(Gtk.Align.CENTER)
        self._light.set_focus_on_click(False)
        self._light.add_css_class("theme-selector")
        self._light.add_css_class("light")
        self._light_check = Gtk.Image.new_from_icon_name("object-select-symbolic")
        self._light_check.add_css_class("theme-check")
        self._light_check.set_halign(Gtk.Align.END)
        self._light_check.set_valign(Gtk.Align.END)
        self._light_check.set_margin_end(2)
        self._light_check.set_margin_bottom(2)
        self._light.set_child(self._light_check)
        inner_box.append(self._light)

        # 3. Dark Style button
        self._dark = Gtk.ToggleButton()
        self._dark.set_tooltip_text("Dark Style")
        self._dark.set_group(self._follow)
        self._dark.set_halign(Gtk.Align.CENTER)
        self._dark.set_valign(Gtk.Align.CENTER)
        self._dark.set_focus_on_click(False)
        self._dark.add_css_class("theme-selector")
        self._dark.add_css_class("dark")
        self._dark_check = Gtk.Image.new_from_icon_name("object-select-symbolic")
        self._dark_check.add_css_class("theme-check")
        self._dark_check.set_halign(Gtk.Align.END)
        self._dark_check.set_valign(Gtk.Align.END)
        self._dark_check.set_margin_end(2)
        self._dark_check.set_margin_bottom(2)
        self._dark.set_child(self._dark_check)
        inner_box.append(self._dark)

        self._follow.connect("toggled", self._on_option_selected)
        self._light.connect("toggled", self._on_option_selected)
        self._dark.connect("toggled", self._on_option_selected)

        self.populate()

    def _on_option_selected(self, _widget: Gtk.ToggleButton):
        if self._updating:
            return
        name = None
        if self._follow.get_active():
            name = "follow"
        elif self._light.get_active():
            name = "light"
        elif self._dark.get_active():
            name = "dark"

        if name:
            self.config_manager.set_theme_mode(name)
            self._apply_style(name)

    def _apply_style(self, style: str):
        manager = Adw.StyleManager.get_default()
        if style == "dark":
            manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        elif style == "light":
            manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        else:
            manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

        if self.on_theme_changed:
            self.on_theme_changed(manager.get_dark())

    def populate(self):
        self._updating = True
        mode = self.config_manager.get_theme_mode()
        if mode == "light":
            self._light.set_active(True)
        elif mode == "dark":
            self._dark.set_active(True)
        else:
            self._follow.set_active(True)
        self._updating = False
