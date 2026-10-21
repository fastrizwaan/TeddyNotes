# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from teddynotes.database import NoteDatabase
from teddynotes.config_manager import ConfigManager
from teddynotes.editor_html import get_editor_html_page
from teddynotes.font_size_selector import FontSizeSelector


class TestThemeAndFont(unittest.TestCase):
    def setUp(self):
        self.db = NoteDatabase(":memory:")
        self.config = ConfigManager(self.db)

    def tearDown(self):
        self.db.close()

    def test_theme_mode_default_and_persistence(self):
        self.assertEqual(self.config.get_theme_mode(), "follow")

        self.config.set_theme_mode("dark")
        self.assertEqual(self.config.get_theme_mode(), "dark")

        self.config.set_theme_mode("light")
        self.assertEqual(self.config.get_theme_mode(), "light")

        # system alias maps to follow
        self.config.set_theme_mode("system")
        self.assertEqual(self.config.get_theme_mode(), "follow")

    def test_font_size_default_and_persistence(self):
        self.assertEqual(self.config.get_font_size(), 16)

        self.config.set_font_size(20)
        self.assertEqual(self.config.get_font_size(), 20)

        self.config.set_font_size(12)
        self.assertEqual(self.config.get_font_size(), 12)

    def test_view_mode_default_and_persistence(self):
        self.assertEqual(self.config.get_view_mode(), "list")

        self.config.set_view_mode("grid")
        self.assertEqual(self.config.get_view_mode(), "grid")

        self.config.set_view_mode("list")
        self.assertEqual(self.config.get_view_mode(), "list")

        # invalid fallback
        self.config.set_view_mode("invalid")
        self.assertEqual(self.config.get_view_mode(), "list")

    def test_font_size_selector_stepping(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")
        selector = FontSizeSelector(self.config)
        self.assertEqual(selector.get_current_size(), 100)

        selector.increase()
        self.assertEqual(selector.get_current_size(), 110)

        selector.increase()
        self.assertEqual(selector.get_current_size(), 120)

        selector.decrease()
        self.assertEqual(selector.get_current_size(), 110)

        selector.reset()
        self.assertEqual(selector.get_current_size(), 100)

    def test_get_editor_html_page_theme_and_font_size(self):
        html_light = get_editor_html_page("<p>Hello</p>", is_dark=False, font_size=16)
        self.assertIn('class="light-theme"', html_light)
        self.assertIn('--base-font-size: 16pt;', html_light)
        self.assertIn('<p>Hello</p>', html_light)

        html_dark = get_editor_html_page("<p>World</p>", is_dark=True, font_size=22)
        self.assertIn('class="dark-theme"', html_dark)
        self.assertIn('--base-font-size: 22pt;', html_dark)
        self.assertIn('<p>World</p>', html_dark)

    def test_typography_config_defaults_and_persistence(self):
        # Card font size
        self.assertEqual(self.config.get_card_font_size(), "default")
        self.config.set_card_font_size("large")
        self.assertEqual(self.config.get_card_font_size(), "large")
        self.config.set_card_font_size("invalid")
        self.assertEqual(self.config.get_card_font_size(), "default")

        # Heading scale
        self.assertEqual(self.config.get_heading_scale(), "normal")
        self.config.set_heading_scale("compact")
        self.assertEqual(self.config.get_heading_scale(), "compact")
        self.config.set_heading_scale("large")
        self.assertEqual(self.config.get_heading_scale(), "large")
        self.config.set_heading_scale("invalid")
        self.assertEqual(self.config.get_heading_scale(), "normal")

        # Code font size
        self.assertEqual(self.config.get_code_font_size(), 14)
        self.config.set_code_font_size(18)
        self.assertEqual(self.config.get_code_font_size(), 18)
        self.config.set_code_font_size(30)  # clamped to 24
        self.assertEqual(self.config.get_code_font_size(), 24)

        # Quote font size
        self.assertEqual(self.config.get_quote_font_size(), 16)
        self.config.set_quote_font_size(20)
        self.assertEqual(self.config.get_quote_font_size(), 20)
        self.config.set_quote_font_size(5)  # clamped to 10
        self.assertEqual(self.config.get_quote_font_size(), 10)

        # Sidebar width
        self.assertEqual(self.config.get_sidebar_width(), 260)
        self.config.set_sidebar_width(340)
        self.assertEqual(self.config.get_sidebar_width(), 340)
        self.config.set_sidebar_width(100)  # clamped to 200
        self.assertEqual(self.config.get_sidebar_width(), 200)

        # Editor mode (default: standard)
        self.assertEqual(self.config.get_editor_mode(), "standard")
        self.config.set_editor_mode("distraction_free")
        self.assertEqual(self.config.get_editor_mode(), "distraction_free")
        self.config.set_editor_mode("invalid")
        self.assertEqual(self.config.get_editor_mode(), "standard")

    def test_get_editor_html_page_full_typography(self):
        html = get_editor_html_page(
            "<p>Test Content</p>",
            is_dark=False,
            font_size=18,
            heading_scale="large",
            code_font_size=15,
            quote_font_size=17
        )
        self.assertIn('--base-font-size: 18pt;', html)
        self.assertIn('--heading-scale: 1.2;', html)
        self.assertIn('--code-font-size: 15px;', html)
        self.assertIn('--quote-font-size: 17pt;', html)
        self.assertIn('<p>Test Content</p>', html)

    def test_notes_list_card_size_classes(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")
        from teddynotes.notes_list import NotesList
        nl = NotesList(self.db)
        self.assertTrue(nl.has_css_class("card-size-default"))
        nl.set_card_size("large")
        self.assertTrue(nl.has_css_class("card-size-large"))
        self.assertFalse(nl.has_css_class("card-size-default"))
        nl.set_card_size("small")
        self.assertTrue(nl.has_css_class("card-size-small"))
        self.assertFalse(nl.has_css_class("card-size-large"))


    def test_editor_font_size_and_zoom_level(self):
        self.assertEqual(self.config.get_editor_font_size(), "default")
        self.assertEqual(self.config.get_editor_zoom_level(), 1.0)
        self.assertEqual(self.config.get_editor_zoom_percent(), 100)

        self.config.set_editor_font_size("small")
        self.assertEqual(self.config.get_editor_font_size(), "small")
        self.assertEqual(self.config.get_editor_zoom_level(), 0.8)
        self.assertEqual(self.config.get_editor_zoom_percent(), 80)

        self.config.set_editor_font_size("large")
        self.assertEqual(self.config.get_editor_font_size(), "large")
        self.assertEqual(self.config.get_editor_zoom_level(), 1.20)
        self.assertEqual(self.config.get_editor_zoom_percent(), 120)

        self.config.set_editor_font_size("xlarge")
        self.assertEqual(self.config.get_editor_font_size(), "xlarge")
        self.assertEqual(self.config.get_editor_zoom_level(), 1.40)
        self.assertEqual(self.config.get_editor_zoom_percent(), 140)

        # Percentage zoom and clamping
        self.config.set_editor_zoom_percent(90)
        self.assertEqual(self.config.get_editor_zoom_percent(), 90)
        self.assertEqual(self.config.get_editor_zoom_level(), 0.9)

        self.config.set_editor_zoom_percent(50)  # clamped to 80
        self.assertEqual(self.config.get_editor_zoom_percent(), 80)

        self.config.set_editor_zoom_percent(200)  # clamped to 160
        self.assertEqual(self.config.get_editor_zoom_percent(), 160)

        # Invalid fallback
        self.config.set_editor_font_size("invalid")
        self.assertEqual(self.config.get_editor_font_size(), "default")
        self.assertEqual(self.config.get_editor_zoom_level(), 1.0)

    def test_get_editor_html_page_with_zoom(self):
        html = get_editor_html_page("<p>Zoom Content</p>", zoom_level=1.2)
        self.assertIn('--base-font-size: 19pt;', html)
        self.assertIn('--code-font-size: 17px;', html)
        self.assertIn('--quote-font-size: 19pt;', html)

    def test_editor_mode_window_hierarchy(self):
        from gi.repository import Gdk, Adw
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")

        from teddynotes.window import TeddyWindow
        app = Adw.Application(application_id="io.github.fastrizwaan.TeddyNotes.TestTheme")
        win = TeddyWindow(app, self.db)

        # Window structure: split_view is root, holding navigation
        self.assertIsInstance(win.get_content(), Adw.OverlaySplitView)
        self.assertEqual(win.split_view.get_content(), win.navigation)

        # Default mode: standard
        self.assertEqual(win.config_manager.get_editor_mode(), "standard")

        # Switch to standard mode
        win.apply_editor_mode("standard")
        self.assertIsInstance(win.get_content(), Adw.OverlaySplitView)
        self.assertEqual(win.split_view.get_content(), win.navigation)

        # Switch back to distraction_free mode
        win.apply_editor_mode("distraction_free")
        self.assertIsInstance(win.get_content(), Adw.OverlaySplitView)
        self.assertEqual(win.split_view.get_content(), win.navigation)

        win.destroy()

    def test_font_family_default_and_persistence(self):
        self.assertEqual(self.config.get_font_family(), "system")
        self.assertIn("Cantarell", self.config.get_font_family_stack())

        self.config.set_font_family("serif")
        self.assertEqual(self.config.get_font_family(), "serif")
        self.assertIn("Charter", self.config.get_font_family_stack())

        self.config.set_font_family("monospace")
        self.assertEqual(self.config.get_font_family(), "monospace")
        self.assertIn("JetBrains Mono", self.config.get_font_family_stack())

        self.config.set_font_family("sans")
        self.assertEqual(self.config.get_font_family(), "sans")
        self.assertIn("Inter", self.config.get_font_family_stack())

        # Normalization of sans-serif / sans_serif
        self.config.set_font_family("sans-serif")
        self.assertEqual(self.config.get_font_family(), "sans")

        # Invalid fallback
        self.config.set_font_family("nonexistent")
        self.assertEqual(self.config.get_font_family(), "system")

    def test_reset_typography_defaults(self):
        self.config.set_card_font_size("large")
        self.config.set_font_family("serif")
        self.config.set_editor_zoom_percent(130)
        self.config.set_heading_scale("large")

        self.config.reset_typography_defaults()
        self.assertEqual(self.config.get_card_font_size(), "default")
        self.assertEqual(self.config.get_font_family(), "system")
        self.assertEqual(self.config.get_editor_zoom_percent(), 100)
        self.assertEqual(self.config.get_heading_scale(), "normal")

    def test_get_editor_html_page_with_font_family(self):
        html_serif = get_editor_html_page("<p>Serif Content</p>", font_family="serif")
        self.assertIn('--font-stack: "Charter"', html_serif)

        html_mono = get_editor_html_page("<p>Mono Content</p>", font_family="monospace")
        self.assertIn('--font-stack: "JetBrains Mono"', html_mono)

        html_sans = get_editor_html_page("<p>Sans Content</p>", font_family="sans")
        self.assertIn('--font-stack: "Inter"', html_sans)

        html_system = get_editor_html_page("<p>System Content</p>", font_family="system")
        self.assertIn('--font-stack: -apple-system', html_system)

    def test_editor_link_styling_and_variables(self):
        html_light = get_editor_html_page("<p>Test</p>", is_dark=False)
        self.assertIn('--link-color: #3584E4;', html_light)
        self.assertIn('--link-hover: #1C71D8;', html_light)
        self.assertIn('a.stilo-link', html_light)

        html_dark = get_editor_html_page("<p>Test</p>", is_dark=True)
        self.assertIn('--link-color: #78AEED;', html_dark)
        self.assertIn('--link-hover: #99C1F1;', html_dark)

    def test_theme_selector_toggles_and_callbacks(self):
        from gi.repository import Gdk, Gtk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")

        from teddynotes.theme_selector import ThemeSelector
        theme_changes = []
        selector = ThemeSelector(self.config, on_theme_changed=lambda is_dark: theme_changes.append(is_dark))

        self.assertIsInstance(selector._follow, Gtk.ToggleButton)
        self.assertIsInstance(selector._light, Gtk.ToggleButton)
        self.assertIsInstance(selector._dark, Gtk.ToggleButton)

        # Initial state follows system
        self.assertTrue(selector._follow.get_active())
        self.assertFalse(selector._light.get_active())
        self.assertFalse(selector._dark.get_active())

        # Select dark
        selector._dark.set_active(True)
        self.assertEqual(self.config.get_theme_mode(), "dark")
        self.assertTrue(selector._dark.get_active())
        self.assertFalse(selector._follow.get_active())
        self.assertIn(True, theme_changes)

        # Select light
        selector._light.set_active(True)
        self.assertEqual(self.config.get_theme_mode(), "light")
        self.assertTrue(selector._light.get_active())
        self.assertFalse(selector._dark.get_active())
        self.assertIn(False, theme_changes)

        # Select follow
        selector._follow.set_active(True)
        self.assertEqual(self.config.get_theme_mode(), "follow")
        self.assertTrue(selector._follow.get_active())

        # Test external config change and populate()
        self.config.set_theme_mode("dark")
        selector.populate()
        self.assertTrue(selector._dark.get_active())


if __name__ == "__main__":
    unittest.main()

