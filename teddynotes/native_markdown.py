# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

"""Native GtkSourceView Markdown editor inspired by Folio's GtkMarkdown.View."""

import re
import base64

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
from gi.repository import Gdk, GLib, Gtk, GtkSource, Pango

from teddynotes.markdown_utils import html_to_markdown, markdown_to_html


class NativeMarkdownView(GtkSource.View):
    """A Markdown source buffer with Folio-style live formatting and HTML clipboard."""

    def __init__(self, on_changed=None, attachment_resolver=None, image_importer=None):
        self.markdown_buffer = GtkSource.Buffer()
        super().__init__(buffer=self.markdown_buffer)
        self.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.set_left_margin(28)
        self.set_right_margin(28)
        self.set_top_margin(24)
        self.set_bottom_margin(32)
        self.set_monospace(False)
        self.set_show_line_numbers(False)
        self.set_tab_width(4)
        self._on_changed = on_changed
        self._attachment_resolver = attachment_resolver
        self._image_importer = image_importer
        self._loading = False
        self._install_tags()
        self.markdown_buffer.connect("changed", self._changed)
        self.markdown_buffer.connect("notify::cursor-position", self._restyle)
        self.markdown_buffer.connect("paste-done", self._paste_done)
        self.connect("copy-clipboard", self._copy_action)
        self.connect("cut-clipboard", self._cut_action)
        self.connect("paste-clipboard", self._paste_action)
        self._install_clipboard_keys()
        self._restyle()

    def _install_tags(self):
        table = self.markdown_buffer.get_tag_table()
        self._tags = {}
        definitions = {
            "h1": {"weight": Pango.Weight.BOLD, "scale": 1.65},
            "h2": {"weight": Pango.Weight.BOLD, "scale": 1.4},
            "h3": {"weight": Pango.Weight.BOLD, "scale": 1.2},
            "h4": {"weight": Pango.Weight.BOLD, "scale": 1.1},
            "h5": {"weight": Pango.Weight.BOLD},
            "h6": {"weight": Pango.Weight.BOLD, "foreground": "#777777"},
            "bold": {"weight": Pango.Weight.BOLD},
            "italic": {"style": Pango.Style.ITALIC},
            "strike": {"strikethrough": True},
            "underline": {"underline": Pango.Underline.SINGLE},
            "highlight": {"background": "#fff2a8"},
            "code": {"family": "monospace", "background": "rgba(127,127,127,0.14)"},
            "quote": {"paragraph-background": "rgba(127,127,127,0.08)", "left-margin": 16},
            "link": {"underline": Pango.Underline.SINGLE, "foreground": "#3584e4"},
            "list": {"left-margin": 18},
            "table": {"family": "monospace"},
            "hidden": {"size": 0},
        }
        for name, props in definitions.items():
            tag = Gtk.TextTag.new("teddy-md-" + name)
            for prop, value in props.items():
                tag.set_property(prop, value)
            table.add(tag)
            self._tags[name] = tag

    def _changed(self, _buffer):
        self._restyle()
        if not self._loading and self._on_changed:
            self._on_changed(self.get_markdown())

    def _range(self, start, end, tag):
        a, b = self.markdown_buffer.get_iter_at_offset(start), self.markdown_buffer.get_iter_at_offset(end)
        self.markdown_buffer.apply_tag(tag, a, b)

    def _restyle(self, *_args):
        if not hasattr(self, "_tags"):
            return
        buf = self.markdown_buffer
        start, end = buf.get_bounds()
        for tag in self._tags.values():
            buf.remove_tag(tag, start, end)
        text = buf.get_text(start, end, True)
        cursor = buf.get_iter_at_mark(buf.get_insert()).get_offset()
        line_start = text.rfind("\n", 0, cursor) + 1
        line_end = text.find("\n", cursor)
        line_end = len(text) if line_end < 0 else line_end

        # Block-level styling mirrors Folio: preserve the Markdown source while
        # formatting it in the native text buffer.
        for match in re.finditer(r"(?m)^ {0,3}(#{1,6})[ \t]+.*$", text):
            level = len(match.group(1))
            self._range(match.start(), match.end(), self._tags[f"h{level}"])
            if not (match.start() <= cursor <= match.end()):
                self._range(match.start(), match.start() + level + 1, self._tags["hidden"])
        for match in re.finditer(r"(?m)^\s*>+.*$", text):
            self._range(match.start(), match.end(), self._tags["quote"])
        for match in re.finditer(r"(?m)^\s*(?:[-+*]|\d+[.)])\s+.*$", text):
            self._range(match.start(), match.end(), self._tags["list"])
        for match in re.finditer(r"(?m)^\s*\|.*\|\s*$", text):
            self._range(match.start(), match.end(), self._tags["table"])

        # Inline tags and marker hiding. Folio reveals the Markdown markers on
        # the active line so the user can edit the source without mode switches.
        patterns = (
            (r"(?<!\\)(\*\*|__)(?=\S)(.+?\S)\1", "bold", (1, 2)),
            (r"(?<![\w\\])([*_])(?=\S)(.+?\S)\1(?!\w)", "italic", (1, 3)),
            (r"~~(?=\S)(.+?\S)~~", "strike", (0, 0)),
            (r"==(?=\S)(.+?\S)==", "highlight", (0, 0)),
            (r"<u>(.+?)</u>", "underline", (0, 0)),
            (r"(?<!`)`([^`\n]+)`(?!`)", "code", (0, 0)),
            (r"!?\[([^\]\n]+)\]\([^\s)]+(?:\s+[^)]*)?\)", "link", (0, 0)),
        )
        for pattern, name, _unused in patterns:
            for match in re.finditer(pattern, text):
                self._range(match.start(), match.end(), self._tags[name])
                if not (line_start <= cursor <= line_end):
                    marker = re.match(r"(?:\*\*|__|~~|==|`|\[|!\[)", match.group(0))
                    if marker:
                        self._range(match.start(), match.start() + len(marker.group(0)), self._tags["hidden"])
                    tail = re.search(r"(?:\*\*|__|~~|==|`|\])(?:\([^)]*\))?$", match.group(0))
                    if tail:
                        self._range(match.end() - len(tail.group(0)), match.end(), self._tags["hidden"])

        for match in re.finditer(r"(?m)^ {0,3}(?:---+|\*\*\*+|___+)\s*$", text):
            self._range(match.start(), match.end(), self._tags["table"])

    def _install_clipboard_keys(self):
        keys = Gtk.EventControllerKey.new()
        keys.connect("key-pressed", self._on_key_pressed)
        self.add_controller(keys)

    def _on_key_pressed(self, _controller, keyval, _keycode, state):
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if not ctrl and keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if self._continue_list():
                return True
        if ctrl and keyval in (Gdk.KEY_c, Gdk.KEY_C):
            return self.copy_markdown_and_html()
        if ctrl and keyval in (Gdk.KEY_x, Gdk.KEY_X):
            self._cut_action(self)
            return True
        if ctrl and keyval in (Gdk.KEY_v, Gdk.KEY_V):
            if state & Gdk.ModifierType.SHIFT_MASK:
                return False
            clipboard = self.get_clipboard()
            if clipboard.get_formats().contain_mime_type("text/html"):
                self._read_html_clipboard()
                return True
        # Plain text/Markdown follows GtkSourceView's native paste action.
        return False

    def _continue_list(self):
        if not self.get_editable():
            return False
        buf = self.markdown_buffer
        cursor = buf.get_iter_at_mark(buf.get_insert())
        start = cursor.copy()
        start.set_line_offset(0)
        end = cursor.copy()
        end.forward_to_line_end()
        line = buf.get_text(start, end, True)
        match = re.match(r"^(\s*)([-+*]|\d+[.)])\s+(.*)$", line)
        if not match:
            return False
        indent, marker, body = match.groups()
        if not body.strip():
            # An empty list item followed by Return exits that list level.
            buf.begin_user_action()
            buf.delete(start, end)
            buf.insert_at_cursor("\n" + indent)
            buf.end_user_action()
            return True
        if marker[0].isdigit():
            number = re.match(r"\d+", marker).group(0)
            continuation = indent + str(int(number) + 1) + marker[len(number):] + " "
        else:
            continuation = indent + marker + " "
        if re.match(r"\[[ xX]\]\s+", body):
            continuation += "[ ] "
        self.insert_text("\n" + continuation)
        return True

    def _copy_action(self, *_args):
        self.stop_emission_by_name("copy-clipboard")
        self.copy_markdown_and_html()

    def _cut_action(self, *_args):
        self.stop_emission_by_name("cut-clipboard")
        if self.get_editable() and self.copy_markdown_and_html():
            self.markdown_buffer.delete_selection(True, True)

    def _paste_action(self, *_args):
        clipboard = self.get_clipboard()
        if clipboard.get_formats().contain_mime_type("text/html"):
            self.stop_emission_by_name("paste-clipboard")
            self._read_html_clipboard()

    def _read_html_clipboard(self):
        self.get_clipboard().read_async(
            ["text/html"], GLib.PRIORITY_DEFAULT, None, self._html_read_ready, None
        )

    def _html_read_ready(self, clipboard, result, _data):
        try:
            stream, _mime_type = clipboard.read_finish(result)
            stream.read_bytes_async(16 * 1024 * 1024, GLib.PRIORITY_DEFAULT, None, self._html_bytes_ready, None)
        except Exception:
            pass

    def _html_bytes_ready(self, stream, result, _data):
        try:
            payload = stream.read_bytes_finish(result).get_data()
            self.paste_html(payload.decode("utf-8", errors="replace"))
        except Exception:
            pass

    def copy_markdown_and_html(self):
        bounds = self.markdown_buffer.get_selection_bounds()
        if not bounds:
            return False
        text = self.markdown_buffer.get_text(bounds[0], bounds[1], True)
        html = markdown_to_html(text)
        if self._attachment_resolver:
            def embed_attachment(match):
                uri = match.group(1)
                resolved = self._attachment_resolver(uri)
                if not resolved:
                    return match.group(0)
                mime_type, payload = resolved
                data_uri = f"data:{mime_type};base64,{base64.b64encode(payload).decode('ascii')}"
                return match.group(0).replace(uri, data_uri, 1)
            html = re.sub(r'(?:src|href)=["\'](attachment://[^"\']+)["\']', embed_attachment, html)
        provider = Gdk.ContentProvider.new_union([
            Gdk.ContentProvider.new_for_bytes("text/plain;charset=utf-8", GLib.Bytes.new(text.encode("utf-8"))),
            Gdk.ContentProvider.new_for_bytes("text/html", GLib.Bytes.new(html.encode("utf-8"))),
        ])
        self.get_clipboard().set_content(provider)
        return True

    def _paste_done(self, _buffer, _clipboard):
        # GTK's native source-view paste handles text/markdown and text/plain.
        # Applications providing HTML can use paste_html() through the same
        # conversion path; images remain Markdown image references/data URIs.
        self._restyle()

    def paste_html(self, html):
        """Insert clipboard HTML as Markdown at the current selection."""
        if not self.get_editable():
            return
        markdown = html_to_markdown(html or "")
        if self._image_importer:
            markdown = self._image_importer(markdown)
        self.markdown_buffer.begin_user_action()
        self.markdown_buffer.delete_selection(True, True)
        self.markdown_buffer.insert_at_cursor(markdown)
        self.markdown_buffer.end_user_action()

    def insert_text(self, text):
        if not self.get_editable():
            return
        buf = self.markdown_buffer
        buf.begin_user_action()
        buf.delete_selection(True, True)
        buf.insert_at_cursor(text)
        buf.end_user_action()

    def format_markdown(self, command):
        """Apply a Markdown edit while keeping the canonical text buffer."""
        if not self.get_editable():
            return
        buf = self.markdown_buffer
        bounds = buf.get_selection_bounds()
        if bounds:
            start, end = bounds
            selected = buf.get_text(start, end, True)
            selected_start = start.get_offset()
            selected_end = end.get_offset()
        else:
            cursor = buf.get_iter_at_mark(buf.get_insert())
            line_start = cursor.copy()
            line_start.set_line_offset(0)
            line_end = cursor.copy()
            line_end.forward_to_line_end()
            selected = buf.get_text(line_start, line_end, True)
            selected_start, selected_end = line_start.get_offset(), line_end.get_offset()
        pairs = {
            "bold": ("**", "**"), "italic": ("*", "*"),
            "strike": ("~~", "~~"), "highlight": ("==", "=="),
            "underline": ("<u>", "</u>"),
            "inline-code": ("`", "`"), "code": ("```\n", "\n```"),
            "quote": ("> ", ""), "todo": ("- [ ] ", ""),
            "bullet": ("- ", ""), "number": ("1. ", ""),
            "link": ("[", "](https://)"), "wiki-link": ("[[", "]]"),
        }
        if command == "undo":
            if buf.can_undo():
                buf.undo()
            return
        if command == "redo":
            if buf.can_redo():
                buf.redo()
            return
        if command.startswith("heading"):
            level = int(command[-1])
            replacement = "#" * level + " " + selected.lstrip("# ")
        elif command == "paragraph":
            replacement = selected.lstrip("# ")
        elif command == "divider":
            replacement = "\n---\n"
        elif command == "clear-format":
            replacement = re.sub(r"(?:\*\*|__|~~|==|[*_`])", "", selected)
        elif command in ("quote", "todo", "bullet", "number"):
            prefix = {"quote": "> ", "todo": "- [ ] ", "bullet": "- ", "number": "1. "}[command]
            replacement = "\n".join(prefix + line if line else prefix.rstrip() for line in selected.split("\n"))
        elif command in pairs:
            left, right = pairs[command]
            replacement = left + selected + right
        else:
            return
        a = buf.get_iter_at_offset(selected_start)
        b = buf.get_iter_at_offset(selected_end)
        buf.begin_user_action()
        buf.delete(a, b)
        buf.insert_at_cursor(replacement)
        buf.end_user_action()

    def insert_table(self, rows=3, cols=3, has_header=True):
        rows, cols = max(1, min(int(rows), 20)), max(1, min(int(cols), 20))
        lines = []
        if has_header:
            lines.append("| " + " | ".join(f"Column {i + 1}" for i in range(cols)) + " |")
            lines.append("| " + " | ".join("---" for _ in range(cols)) + " |")
            rows -= 1
        lines.extend("| " + " | ".join(" " for _ in range(cols)) + " |" for _ in range(max(0, rows)))
        self.insert_text("\n" + "\n".join(lines) + "\n")

    def insert_link(self, label, url):
        if not self.get_editable():
            return
        buf = self.markdown_buffer
        bounds = buf.get_selection_bounds()
        if bounds:
            selected = buf.get_text(bounds[0], bounds[1], True)
            label = label or selected or url
            a, b = bounds
            buf.delete(a, b)
        else:
            label = label or url
        buf.insert_at_cursor(f"[{label}]({url})")

    def set_markdown(self, markdown):
        self._loading = True
        self.markdown_buffer.set_text(markdown or "", -1)
        self._loading = False
        self._restyle()

    def get_markdown(self):
        start, end = self.markdown_buffer.get_bounds()
        return self.markdown_buffer.get_text(start, end, True)
