# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from teddynotes.database import NoteDatabase
from teddynotes.config_manager import ConfigManager
from teddynotes.models import Category
from teddynotes.sidebar import Sidebar, _build_category_tree


class TestSidebarTreeAndCollapse(unittest.TestCase):
    def setUp(self):
        self.db = NoteDatabase(":memory:")
        self.config = ConfigManager(self.db)

    def tearDown(self):
        self.db.close()

    def test_build_category_tree_flat(self):
        cats = [Category(id="1", name="Work"), Category(id="2", name="Personal")]
        tree = _build_category_tree(cats)
        # Preserves user-defined category order
        self.assertEqual(len(tree), 2)
        self.assertEqual(tree[0], ("Work", 0, "Work", False))
        self.assertEqual(tree[1], ("Personal", 0, "Personal", False))

    def test_build_category_tree_nested(self):
        cats = [
            Category(id="1", name="Personal"),
            Category(id="2", name="Personal/Due"),
            Category(id="3", name="Personal/Due/Urgent"),
            Category(id="4", name="Work"),
        ]
        tree = _build_category_tree(cats)
        self.assertEqual(len(tree), 4)

        # 1. Personal (depth 0, has_children=True)
        self.assertEqual(tree[0], ("Personal", 0, "Personal", True))
        # 2. Personal/Due (depth 1, has_children=True)
        self.assertEqual(tree[1], ("Personal/Due", 1, "Due", True))
        # 3. Personal/Due/Urgent (depth 2, has_children=False)
        self.assertEqual(tree[2], ("Personal/Due/Urgent", 2, "Urgent", False))
        # 4. Work (depth 0, has_children=False)
        self.assertEqual(tree[3], ("Work", 0, "Work", False))

    def test_build_category_tree_implicit_parent(self):
        # Category where parent was not separately created in db
        cats = [Category(id="1", name="Projects/Alpha/Tasks")]
        tree = _build_category_tree(cats)
        self.assertEqual(len(tree), 3)
        self.assertEqual(tree[0], ("Projects", 0, "Projects", True))
        self.assertEqual(tree[1], ("Projects/Alpha", 1, "Alpha", True))
        self.assertEqual(tree[2], ("Projects/Alpha/Tasks", 2, "Tasks", False))

    def test_category_visibility_logic(self):
        # Simulate _is_category_visible logic
        def is_visible(collapsed: set, cat_name: str) -> bool:
            parts = cat_name.split("/")
            for i in range(1, len(parts)):
                if "/".join(parts[:i]) in collapsed:
                    return False
            return True

        collapsed = set()
        self.assertTrue(is_visible(collapsed, "Personal"))
        self.assertTrue(is_visible(collapsed, "Personal/Due"))
        self.assertTrue(is_visible(collapsed, "Personal/Due/Urgent"))

        # Collapse root: Personal
        collapsed.add("Personal")
        self.assertTrue(is_visible(collapsed, "Personal"))  # Root itself is visible
        self.assertFalse(is_visible(collapsed, "Personal/Due"))
        self.assertFalse(is_visible(collapsed, "Personal/Due/Urgent"))
        self.assertTrue(is_visible(collapsed, "Work"))

        # Uncollapse Personal, collapse Personal/Due
        collapsed.remove("Personal")
        collapsed.add("Personal/Due")
        self.assertTrue(is_visible(collapsed, "Personal"))
        self.assertTrue(is_visible(collapsed, "Personal/Due"))  # Due itself is visible
        self.assertFalse(is_visible(collapsed, "Personal/Due/Urgent"))  # Children hidden

    def test_config_manager_collapsed_persistence(self):
        self.assertEqual(self.config.get_collapsed_categories(), set())

        self.config.set_collapsed_categories({"Personal", "Work/Projects"})
        loaded = self.config.get_collapsed_categories()
        self.assertEqual(loaded, {"Personal", "Work/Projects"})

        self.config.set_collapsed_categories(set())
        self.assertEqual(self.config.get_collapsed_categories(), set())


    def test_sidebar_title_and_order(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")

        from teddynotes.sidebar import Sidebar
        sidebar = Sidebar(self.db)
        self.assertEqual(sidebar.window_title.get_title(), "Teddy Notes")

        # Inspect rows
        rows = []
        for i in range(10):
            r = sidebar.listbox.get_row_at_index(i)
            if not r:
                break
            filter_type = getattr(r, "_filter_type", None)
            if filter_type:
                rows.append(filter_type)

        # Expected order: all, favorites, todos, lists, linked, private, uncategorized
        self.assertEqual(rows[:7], ["all", "favorites", "todos", "lists", "linked", "private", "uncategorized"])

    def test_todo_filtering_with_brackets(self):
        # Clean db notes
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM notes")
            conn.commit()

        # Note 1: has [ ] checklist
        self.db.create_note(title="Todo Note", initial_text="Shopping:\n[ ] Buy apples\n[ ] Buy milk")
        # Note 2: has - [x] checklist
        self.db.create_note(title="Done Note", initial_text="Task:\n- [x] Finished item")
        # Note 3: regular note
        self.db.create_note(title="Regular Note", initial_text="Just a note without checkboxes")

        counts = self.db.get_counts()
        self.assertEqual(counts["all"], 3)
        self.assertEqual(counts["todos"], 2)

        todo_notes = self.db.get_notes(filter_type="todos")
        self.assertEqual(len(todo_notes), 2)
        titles = {n.title for n in todo_notes}
        self.assertEqual(titles, {"Todo Note", "Done Note"})

    def test_lists_filtering_with_bullet_and_number(self):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM notes")
            conn.commit()

        # Note 1: bullet list with *
        self.db.create_note(title="Star List", initial_text="* Item 1\n* Item 2")
        # Note 2: numbered list with 1.
        self.db.create_note(title="Numbered List", initial_text="1. First\n2. Second")
        # Note 3: bullet list with -
        self.db.create_note(title="Dash List", initial_text="- Point A\n- Point B")
        # Note 4: checklist only (should NOT count as bullet list)
        self.db.create_note(title="Only Checklist", initial_text="- [ ] Task A\n- [ ] Task B")
        # Note 5: plain note
        self.db.create_note(title="Plain", initial_text="Simple text without lists")

        counts = self.db.get_counts()
        self.assertEqual(counts["all"], 5)
        self.assertEqual(counts["lists"], 3)

        list_notes = self.db.get_notes(filter_type="lists")
        self.assertEqual(len(list_notes), 3)
        titles = {n.title for n in list_notes}
        self.assertEqual(titles, {"Star List", "Numbered List", "Dash List"})

    def test_category_and_subcategory_note_counts(self):
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM notes")
            conn.execute("DELETE FROM categories")
            conn.commit()

        # Create category hierarchy: C, C/sd, C/Computer Networks, C/Personal, C/Work
        self.db.create_category("C")
        self.db.create_category("C/sd")
        self.db.create_category("C/Computer Networks")
        self.db.create_category("C/Personal")
        self.db.create_category("C/Work")

        # 1 note in C
        self.db.create_note(title="C Root Note", category="C")
        # 2 notes in C/sd
        self.db.create_note(title="SD Note 1", category="C/sd")
        self.db.create_note(title="SD Note 2", category="C/sd")
        # 1 note in C/Personal
        self.db.create_note(title="Personal Note 1", category="C/Personal")
        # 0 notes in C/Computer Networks
        # 0 notes in C/Work

        counts = self.db.get_counts()

        # C has 1 direct note + 2 in C/sd + 1 in C/Personal = 4 notes.
        # Subcategories themselves (4 subcategories) must NOT be counted as notes!
        self.assertEqual(counts.get("cat:C", 0), 4)
        self.assertEqual(counts.get("cat:C/sd", 0), 2)
        self.assertEqual(counts.get("cat:C/Personal", 0), 1)
        self.assertEqual(counts.get("cat:C/Computer Networks", 0), 0)
        self.assertEqual(counts.get("cat:C/Work", 0), 0)

        # In get_categories() as well
        cats = {c.name: c.count for c in self.db.get_categories()}
        self.assertEqual(cats["C"], 4)
        self.assertEqual(cats["C/sd"], 2)
        self.assertEqual(cats["C/Personal"], 1)
        self.assertEqual(cats["C/Computer Networks"], 0)
        self.assertEqual(cats["C/Work"], 0)

        # When filtering by category "C", exactly 4 notes returned
        c_notes = self.db.get_notes(filter_type="category", category_name="C")
        self.assertEqual(len(c_notes), 4)

    def test_rename_subcategory_preserves_path_and_leaf_name(self):
        # Category: Personal/Work/Projects
        old_name = "Personal/Work/Projects"
        display_name = old_name.split("/")[-1]
        self.assertEqual(display_name, "Projects")

        # When renamed to new leaf "Tasks"
        new_leaf = "Tasks"
        if "/" in old_name:
            parent_path = old_name.rsplit("/", 1)[0]
            new_name = f"{parent_path}/{new_leaf}"
        else:
            new_name = new_leaf

        self.assertEqual(new_name, "Personal/Work/Tasks")

        # Test with DB operations
        self.db.create_category("Personal")
        self.db.create_category("Personal/Work")
        self.db.create_category(old_name)
        note = self.db.create_note(title="Project Note", category=old_name)

        self.db.rename_category(old_name, new_name)
        updated_note = self.db.get_note(note.id)
        self.assertEqual(updated_note.category, "Personal/Work/Tasks")

        # Test top-level category rename
        top_old = "Personal"
        top_display = top_old.split("/")[-1]
        self.assertEqual(top_display, "Personal")
        top_new_leaf = "Life"
        if "/" in top_old:
            parent_path = top_old.rsplit("/", 1)[0]
            top_new = f"{parent_path}/{top_new_leaf}"
        else:
            top_new = top_new_leaf
        self.assertEqual(top_new, "Life")

        self.db.rename_category(top_old, top_new)
        updated_note = self.db.get_note(note.id)
        self.assertEqual(updated_note.category, "Life/Work/Tasks")


class TestToolbarPin(unittest.TestCase):
    def setUp(self):
        self.db = NoteDatabase(":memory:")
        self.config = ConfigManager(self.db)

    def tearDown(self):
        self.db.close()

    def test_toolbar_pinned_config(self):
        self.assertFalse(self.config.get_toolbar_pinned())
        self.config.set_toolbar_pinned(True)
        self.assertTrue(self.config.get_toolbar_pinned())
        self.config.set_toolbar_pinned(False)
        self.assertFalse(self.config.get_toolbar_pinned())

    def test_formatting_bar_no_pin_button(self):
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Gdk, Gtk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")
        from teddynotes.editor import FormattingBar
        bar = FormattingBar(exec_fn=lambda c: None)
        self.assertFalse(hasattr(bar, "pin_btn"))


class TestSidebarSplitterResizer(unittest.TestCase):
    def setUp(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")
        self.db = NoteDatabase(":memory:")
        self.config = ConfigManager(self.db)

    def tearDown(self):
        self.db.close()

    def test_sidebar_drag_calculation_and_clamping(self):
        from unittest.mock import MagicMock
        from teddynotes.sidebar import Sidebar

        sidebar = Sidebar(self.db)
        sidebar._drag_start_width = 260
        sidebar._mouse_edge_offset = 3.0  # mouse was clicked 3px from sidebar right edge

        # Mock gesture without event position -> fallback to offset_x
        mock_gesture = MagicMock()
        mock_gesture.get_current_sequence.return_value = None
        mock_gesture.get_last_event.return_value = None
        mock_gesture.get_current_event.return_value = None

        # Test fallback
        sidebar._mouse_edge_offset = None
        w1 = sidebar._calculate_target_width(mock_gesture, offset_x=20)
        self.assertEqual(w1, 280)

        # Clamping minimum (200px)
        w_min = sidebar._calculate_target_width(mock_gesture, offset_x=-100)
        self.assertEqual(w_min, 200)

        # Clamping maximum (500px)
        w_max = sidebar._calculate_target_width(mock_gesture, offset_x=300)
        self.assertEqual(w_max, 500)

    def test_sidebar_drag_signals_and_persistence(self):
        from unittest.mock import MagicMock
        from teddynotes.sidebar import Sidebar

        sidebar = Sidebar(self.db)
        dragged_widths = []
        ended_widths = []

        sidebar.connect("width-dragged", lambda _sb, w: dragged_widths.append(w))
        sidebar.connect("width-drag-ended", lambda _sb, w: ended_widths.append(w))

        mock_gesture = MagicMock()
        mock_gesture.get_current_sequence.return_value = None
        mock_gesture.get_last_event.return_value = None
        mock_gesture.get_current_event.return_value = None

        sidebar._on_resizer_drag_begin(mock_gesture, 3, 100)
        self.assertTrue(sidebar.drag_handle.has_css_class("dragging"))

        # Move to +15px
        sidebar._on_resizer_drag_update(mock_gesture, offset_x=15, offset_y=0)
        self.assertEqual(dragged_widths, [275])

        # Same width movement: duplicate must be suppressed
        sidebar._on_resizer_drag_update(mock_gesture, offset_x=15.2, offset_y=0)
        self.assertEqual(len(dragged_widths), 1)

        # Move to +25px
        sidebar._on_resizer_drag_update(mock_gesture, offset_x=25, offset_y=0)
        self.assertEqual(dragged_widths, [275, 285])

        # Release drag
        sidebar._on_resizer_drag_end(mock_gesture, offset_x=25, offset_y=0)
        self.assertFalse(sidebar.drag_handle.has_css_class("dragging"))
        self.assertEqual(ended_widths, [285])
        self.assertEqual(self.config.get_sidebar_width(), 285)

    def test_window_constraint_ordering_never_violates_min_max(self):
        """Verify min_sidebar_width is never strictly greater than max_sidebar_width."""
        from gi.repository import Adw
        split_view = Adw.OverlaySplitView()
        split_view.set_min_sidebar_width(260)
        split_view.set_max_sidebar_width(260)

        # Expanding: 260 -> 300
        new_width = 300
        cur_max = int(split_view.get_max_sidebar_width())
        if new_width > cur_max:
            split_view.set_max_sidebar_width(new_width)
            self.assertLessEqual(split_view.get_min_sidebar_width(), split_view.get_max_sidebar_width())
            split_view.set_min_sidebar_width(new_width)
            self.assertEqual(split_view.get_min_sidebar_width(), split_view.get_max_sidebar_width())

        # Shrinking: 300 -> 220
        new_width = 220
        cur_max = int(split_view.get_max_sidebar_width())
        if new_width <= cur_max:
            split_view.set_min_sidebar_width(new_width)
            self.assertLessEqual(split_view.get_min_sidebar_width(), split_view.get_max_sidebar_width())
            split_view.set_max_sidebar_width(new_width)
            self.assertEqual(split_view.get_min_sidebar_width(), split_view.get_max_sidebar_width())


class TestSidebarSectionHeadersAndAlignment(unittest.TestCase):
    def setUp(self):
        self.db = NoteDatabase(":memory:")
        self.config = ConfigManager(self.db)

    def tearDown(self):
        self.db.close()

    def test_categories_and_tags_expansion_persistence(self):
        self.assertTrue(self.config.get_categories_expanded())
        self.assertTrue(self.config.get_tags_expanded())

        self.config.set_categories_expanded(False)
        self.assertFalse(self.config.get_categories_expanded())

        self.config.set_tags_expanded(False)
        self.assertFalse(self.config.get_tags_expanded())

        self.config.set_categories_expanded(True)
        self.assertTrue(self.config.get_categories_expanded())

    def test_tag_rename_and_delete_in_database(self):
        note1 = self.db.create_note(title="Note 1", initial_text="hello", tags=["alpha", "beta"])
        note2 = self.db.create_note(title="Note 2", initial_text="world", tags=["alpha", "omega"])

        self.db.rename_tag("alpha", "gamma")
        n1 = self.db.get_note(note1.id)
        n2 = self.db.get_note(note2.id)
        self.assertIn("gamma", n1.tags)
        self.assertNotIn("alpha", n1.tags)
        self.assertIn("gamma", n2.tags)
        self.assertNotIn("alpha", n2.tags)

        self.db.delete_tag("beta")
        n1 = self.db.get_note(note1.id)
        self.assertNotIn("beta", n1.tags)
        self.assertIn("gamma", n1.tags)

    def test_sidebar_section_headers_alignment_and_expansion(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")

        from teddynotes.sidebar import Sidebar
        self.db.create_category("Personal")
        self.db.create_category("Personal/Projects")
        self.db.create_note(title="Tag Note", tags=["important"])

        sidebar = Sidebar(self.db)

        # Find rows
        cat_header_row = None
        tag_header_row = None
        for i in range(50):
            r = sidebar.listbox.get_row_at_index(i)
            if not r:
                break
            ft = getattr(r, "_filter_type", None)
            if ft == "categories_header":
                cat_header_row = r
            elif ft == "tags_header":
                tag_header_row = r

        self.assertIsNotNone(cat_header_row)
        self.assertIsNotNone(tag_header_row)

        # Verify left alignment: 1st category (depth 0) must align left (margin_start == 0)
        row_root_cat = sidebar._category_rows.get("Personal")
        self.assertIsNotNone(row_root_cat)
        box_root = row_root_cat.get_child()
        self.assertEqual(box_root.get_margin_start(), 0)

        # Subcategory (depth 1) must be indented
        row_sub_cat = sidebar._category_rows.get("Personal/Projects")
        self.assertIsNotNone(row_sub_cat)
        box_sub = row_sub_cat.get_child()
        self.assertEqual(box_sub.get_margin_start(), 16)

        # Initial state: expanded by default -> chevron is hidden, + button is visible
        self.assertFalse(sidebar._categories_chevron_btn.get_visible())
        self.assertTrue(sidebar._categories_add_btn.get_visible())
        self.assertFalse(sidebar._tags_chevron_btn.get_visible())
        self.assertTrue(sidebar._tags_add_btn.get_visible())

        # Toggle categories section: should hide category rows and + button, SHOW > chevron
        self.assertTrue(row_root_cat.get_visible())
        sidebar._on_toggle_categories_section()
        self.assertFalse(sidebar._categories_expanded)
        self.assertFalse(row_root_cat.get_visible())
        self.assertFalse(row_sub_cat.get_visible())
        self.assertTrue(sidebar._categories_chevron_btn.get_visible())
        self.assertFalse(sidebar._categories_add_btn.get_visible())

        # Toggle again: should show category rows and + button, HIDE chevron
        sidebar._on_toggle_categories_section()
        self.assertTrue(sidebar._categories_expanded)
        self.assertTrue(row_root_cat.get_visible())
        self.assertFalse(sidebar._categories_chevron_btn.get_visible())
        self.assertTrue(sidebar._categories_add_btn.get_visible())

        # Toggle tags section: should hide tags and + button, SHOW > chevron
        row_tag = sidebar._tag_rows.get("important")
        self.assertIsNotNone(row_tag)
        self.assertTrue(row_tag.get_visible())
        sidebar._on_toggle_tags_section()
        self.assertFalse(sidebar._tags_expanded)
        self.assertFalse(row_tag.get_visible())
        self.assertTrue(sidebar._tags_chevron_btn.get_visible())
        self.assertFalse(sidebar._tags_add_btn.get_visible())

        sidebar._on_toggle_tags_section()
        self.assertTrue(sidebar._tags_expanded)
        self.assertTrue(row_tag.get_visible())
        self.assertFalse(sidebar._tags_chevron_btn.get_visible())
        self.assertTrue(sidebar._tags_add_btn.get_visible())

    def test_window_on_sidebar_filter_changed_argument_flexibility(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")

        from gi.repository import Adw
        from teddynotes.window import TeddyWindow
        app = Adw.Application(application_id="io.github.fastrizwaan.TeddyNotes.TestSidebar")
        win = TeddyWindow(app, self.db)

        # Should accept 3 args (Gtk signal handler style: self, sender, filter_type, category_name)
        win.on_sidebar_filter_changed(win.sidebar, "category", "Personal")

        # Should also accept 2 args without error (self, filter_type, category_name)
        win.on_sidebar_filter_changed("category", "Personal")

        # Should accept no args
        win.on_sidebar_filter_changed()

        win.destroy()

    def test_sidebar_refresh_updates_new_tags_and_counts(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")

        from teddynotes.sidebar import Sidebar
        note = self.db.create_note(title="App Note", tags=["initial_tag"])
        sidebar = Sidebar(self.db)
        sidebar.refresh()

        self.assertIn("initial_tag", sidebar._tag_rows)
        self.assertNotIn("my_apps", sidebar._tag_rows)

        # Update note with new tag
        self.db.save_note(note.id, tags=["initial_tag", "my_apps"])
        sidebar.refresh()

        self.assertIn("initial_tag", sidebar._tag_rows)
        self.assertIn("my_apps", sidebar._tag_rows)

    def test_window_on_note_updated_refreshes_sidebar(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")

        from gi.repository import Adw
        from teddynotes.window import TeddyWindow
        app = Adw.Application(application_id="io.github.fastrizwaan.TeddyNotes.TestSidebar")
        win = TeddyWindow(app, self.db)
        note = win.db.create_note(title="Task Note", tags=["task"])
        win.sidebar.refresh()
        self.assertIn("task", win.sidebar._tag_rows)
        self.assertNotIn("my_apps", win.sidebar._tag_rows)

        # Simulate note updated from editor
        win.db.save_note(note.id, tags=["task", "my_apps"])
        win._on_note_updated(win.editor, note.id, "Task Note", "", "", "", ["task", "my_apps"], False)
        if getattr(win, "_run_note_updated_refresh", None):
            win._run_note_updated_refresh()

        self.assertIn("my_apps", win.sidebar._tag_rows)
        win.destroy()

    def test_database_reorder_categories(self):
        self.db.create_category("Alpha")
        self.db.create_category("Beta")
        self.db.create_category("Gamma")
        cats = [c.name for c in self.db.get_categories() if c.name in ("Alpha", "Beta", "Gamma")]
        self.assertEqual(cats, ["Alpha", "Beta", "Gamma"])

        # Reorder Gamma, Alpha, Beta
        all_cats = [c.name for c in self.db.get_categories()]
        others = [c for c in all_cats if c not in ("Alpha", "Beta", "Gamma")]
        self.db.reorder_categories(others + ["Gamma", "Alpha", "Beta"])
        reordered = [c.name for c in self.db.get_categories() if c.name in ("Alpha", "Beta", "Gamma")]
        self.assertEqual(reordered, ["Gamma", "Alpha", "Beta"])

    def test_sidebar_on_reorder_category(self):
        from gi.repository import Gdk
        if Gdk.Display.get_default() is None:
            raise unittest.SkipTest("No Gdk.Display available (headless)")
        sidebar = Sidebar(self.db)
        self.db.create_category("CatA")
        self.db.create_category("CatB")
        self.db.create_category("CatC")
        sidebar.refresh()

        # Drag CatC before CatA
        res = sidebar._on_reorder_category("CatC", "CatA", after=False)
        self.assertTrue(res)
        cats = [c.name for c in self.db.get_categories() if c.name in ("CatA", "CatB", "CatC")]
        self.assertEqual(cats, ["CatC", "CatA", "CatB"])

        # Drag CatC after CatB
        res = sidebar._on_reorder_category("CatC", "CatB", after=True)
        self.assertTrue(res)
        cats = [c.name for c in self.db.get_categories() if c.name in ("CatA", "CatB", "CatC")]
        self.assertEqual(cats, ["CatA", "CatB", "CatC"])


if __name__ == "__main__":
    unittest.main()


