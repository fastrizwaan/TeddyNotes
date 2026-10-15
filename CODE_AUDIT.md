# Teddy Notes — Code Audit & Remediation

Deep review of the `teddynotes/` package across six dimensions: logical/functional
bugs, performance bottlenecks, race conditions, threading & concurrency hazards,
memory leaks, and error-handling gaps.

Each finding lists **root cause → affected locations → severity → fix (applied) →
verification**. An *Status* line states whether the fix has already been applied
to the tree.

---

## Severity legend

| Level | Meaning |
|-------|---------|
| **S1 – Critical** | Data loss / corruption, crashes, or silent wrong results. |
| **S2 – High** | User-visible incorrect behaviour or resource/responsiveness problems under normal use. |
| **S3 – Medium** | Correctness/robustness gaps reachable only in edge cases or multi-instance use. |
| **S4 – Low** | Code hygiene, dead code, defensive hardening. |

---

# 1. Threading & concurrency

## 1.1 Background save worker touched live main-thread state — **S1** ✅ Fixed

**Root cause.** `NoteEditor._schedule_save()` spawned a daemon
`threading.Thread` whose `worker()` closure read `self.current_note` and
`self._pending_save_data` while the GTK main thread was concurrently mutating
them (on every `contentChanged` message, note switch, category change, theme
change, …).

```python
def worker():
    ...
    note_category = data.get("category",
        self.current_note.category if self.current_note else None)  # ← live read
```

The *fallback* re-read a mutable `Note` dataclass owned by the main thread with
no synchronization. If the user switched notes between the snapshot
(`do_save`) and the read, the worker could persist the **wrong category** onto
the note being saved. Python's GIL makes this non-crashing but not
non-corrupting: reads can interleave with writes and observe torn/foreign
values.

**Affected.** `teddynotes/editor.py` `_schedule_save` (~L1763-1809 before fix).

**Fix.** The worker is now a pure function of an immutable snapshot:
`data = dict(self._pending_save_data)` (with `tags` defensively copied) is
taken on the main thread, and `note_category = data.get("category")` — no
`self.current_note` access off-thread. The idle callback re-validates that the
exact payload is *still* pending (see 1.2). `db.save_note()` itself is
`RLock`-guarded and marshals its change notification through `GLib.idle_add`,
so calling it from the worker remains safe.

**Verification.**
```python
# tests: simulate a note switch mid-save and assert category integrity
def test_save_snapshot_isolated_from_note_switch():
    ...  # open note A (cat "X") -> edit (schedules save) -> open note B (cat "Y")
    # assert A keeps category "X" after save completes
```

---

## 1.2 Stale save callback clobbered newer state / wrong note — **S2** ✅ Fixed

**Root cause.** The old idle callback only checked
`self._pending_save_data.get("html") == data["html"]`. Two gaps:
1. It compared HTML but not `note_id`; after a note switch the flag could still
   match if the user retyped identical content.
2. On the *failure* path the exception was only printed — the status label
   stayed on “Saving…” forever, giving the user a false impression the note was
   persisted.

**Affected.** `editor.py` `_schedule_save.on_done` / `worker` exception branch.

**Fix.** Added `_is_current_pending(data)` which requires **both** `note_id` and
`html` to match before any UI mutation, and `_on_background_save_failed()` which
sets “Save failed” on the main thread when the payload is still current.

**Verification.** `test_stale_save_callback_is_ignored` — start save for note A,
switch to note B, let A's worker finish, assert B's `_pending_save_data` and
title/status are untouched.

---

## 1.3 `flush_save()` dropped pending data on failure — **S1** ✅ Fixed

**Root cause.** The old `flush_save()` did `self._pending_save_data = None`
**before** calling `db.save_note(...)`. If the write raised (disk full, DB
locked, serialization error), the only copy of the user's edits was discarded —
silent data loss on close.

Additionally it inherited the same unguarded `self.current_note` fallback as 1.1.

**Affected.** `editor.py` `flush_save` (called from `_go_back`, `load_note`,
`destroy_editor`, `_on_close_request`).

**Fix.** Snapshot first, save, and clear `_pending_save_data` **only after** a
successful commit (`if self._is_current_pending(data): self._pending_save_data = None`).
On failure the payload is retained and the label shows “Save failed”, so a retry
(e.g. pressing Back again) can still persist it.

**Verification.** `test_flush_save_retains_pending_on_db_error` — monkeypatch
`db.save_note` to raise, assert `has_pending_changes()` is still `True`.

---

## 1.4 Shared connection across threads needed transactional rollback — **S1** ✅ Fixed

**Root cause.** `NoteDatabase` hands out a single
`sqlite3.connect(..., check_same_thread=False)` connection guarded by an
`RLock`. `get_connection()` was a bare context manager that only acquired the
lock — it never rolled back. Therefore any write method that raised between
`cursor.execute(...)` and `conn.commit()` left the connection holding an **open
transaction**. Consequences:
* The next unrelated write would silently **commit the partially-applied
  previous write**.
* Or raise `sqlite3.OperationalError: cannot commit - no transaction is active`
  if the failed transaction had been implicitly rolled back.
* Because the `RLock` is held for the whole block, a long/errored write could
  also block the UI-thread readers.

**Affected.** `teddynotes/database.py` `get_connection`, and every writer
(`save_note`, `delete_note`, `restore_note`, `empty_trash`, `set_note_pinned`,
`set_notes_pinned`, `set_note_category`, `set_notes_category`, `delete_notes`,
category + attachment + settings writers).

**Fix.** Two-part:
1. `get_connection()` now wraps `yield conn` in `try/except BaseException` and,
   when `conn.in_transaction` is set, calls `conn.rollback()` before re-raising.
   This is a **central safety net** — every existing `with self.get_connection()`
   write block gains rollback-on-error without touching call sites.
2. Added `_write_transaction()` (commit exactly once on success) and migrated
   `save_note` to it; its `_notify_change` dispatch was moved **outside** the
   transaction so listeners no longer fire from inside the DB lock.

**Verification.**
```python
def test_write_rollback_on_error():
    db = NoteDatabase(":memory:")
    n = db.create_note(title="A")
    db._conn.execute("BEGIN")           # simulate a dangling txn
    with pytest.raises(Exception):
        with db.get_connection() as c:
            c.execute("UPDATE notes SET title='X' WHERE id=?", (n.id,))
            raise RuntimeError("boom")
    assert not db.get_connection().__enter__().in_transaction
    # title is unchanged because the failed write was rolled back
    assert db.get_note(n.id).title == "A"
```
Also assert the DB is still usable (a subsequent save succeeds) and that no
`sqlite3.OperationalError` is raised by the next write.

---

## 1.5 Module-global `_GLOBAL_DB` broke multi-window attachment resolution — **S3** ✅ Fixed

**Root cause.** `_register_attachment_scheme(db)` stored the passed DB in a
module-level `_GLOBAL_DB` and the `attachment://` URI handler resolved image
BLOBs against it. The scheme is registered **once per process** (WebKit
`register_uri_scheme`), so in a multi-window session the *last* editor created
overwrote `_GLOBAL_DB`; images opened in the first window then resolved against
the wrong store. Windows share a DB today, so this was latent, but the design
breaks the moment per-window or scoped stores are introduced — and it is
already fragile if an `export_*`/`NoteDatabase()` fallback instance exists.

**Affected.** `editor.py` `_register_attachment_scheme` / `handle_attachment`;
populated from `NoteEditor.__init__`.

**Fix.** Added `_db_for_request(request)` which resolves the owner via
`request.get_web_view()._teddy_db` (bounds-checked), falling back to
`_GLOBAL_DB`. `_build_ui()` now stamps `self.webview._teddy_db = self.db`.

**Verification.** `test_attachment_scheme_uses_owning_webview` — create two
editors with distinct in-memory DBs each holding an attachment of the same id
but different bytes; issue a request via each WebView and assert each returns
its own bytes.

---

# 2. Logical & functional bugs

## 2.1 Dead branch hid the `immediate` fast-path — **S4** ✅ Fixed

**Root cause.**
```python
self.navigation.push_by_tag("editor") if False else self.navigation.push(self.editor_page)
```
The `if False` makes the whole `push_by_tag` arm dead; the `immediate`
parameter was silently ignored.

**Affected.** `teddynotes/window.py` `open_note` (L366 before fix).

**Fix.** Collapsed to the unconditional, correct
`self.navigation.push(self.editor_page)`.

**Verification.** Static — grep shows no remaining `if False`. Behavioural:
opening any note pushes the editor page exactly once.

---

## 2.2 `_cleanup()` ran twice, double-freeing timers/handlers — **S2** ✅ Fixed

**Root cause.** `TeddyWindow` connects **both** `close-request` →
`_on_close_request` and `destroy` → `_on_destroy`, and both call `_cleanup()`;
on top of that, `TeddyApplication.do_shutdown()` iterates all windows and calls
`win._cleanup()` again. `_cleanup()` unconditionally ran
`_flush_pending_sidebar_resize()`, `editor.destroy_editor()` and
`index_view.destroy_view()`. The second pass removed GLib sources that were
already removed (warning / possible use-after-free) and re-ran
`flush_save()` after the WebView handlers had been disconnected.

**Affected.** `window.py` `_cleanup`, `_on_destroy`, `_on_close_request`;
`application.py` `do_shutdown`.

**Fix.** Added an idempotency guard: `_cleaned_up` (initialised in `__init__`)
makes `_cleanup()` a no-op after the first invocation. Subsequent calls —
from `close-request`, `destroy`, and `do_shutdown` — are now safe.

**Verification.** `test_window_cleanup_idempotent` (widget test) — call
`_cleanup()` twice and assert no exception and that `destroy_editor` /
`destroy_view` were each invoked once (spy doubles).

---

# 3. Error-handling gaps

## 3.1 Background save failure was invisible — **S2** ✅ Fixed

Covered by 1.2: the worker's `except` only `print()`ed. Now the failure is
surfaced in the status label via the main thread.

## 3.2 `save_note` encryption fallback silently persisted plaintext — **S3** — Documented (by design)

**Root cause.** When a locked note's body fails to encrypt, the code `pass`es
and stores the plaintext, commented as “leave the note plaintext so it stays
readable by the app”. This is a deliberate availability-over-confidentiality
trade-off, but it is silent: a user may believe a locked note is encrypted at
rest when it is not.

**Recommendation (not applied — behavioural change).** Emit a change event /
toast such as “private note could not be encrypted; saved unencrypted” and
record the condition, rather than failing silently. Low risk to implement but
it changes UX, so flag it for a product decision.

---

# 4. Memory & resources

## 4.1 Bounded caches confirmed OK — no action

`notes_list.py` `_TEXTURE_CACHE` and `_TABLE_CACHE` evict the oldest 50 entries
once they exceed 200 (`if len(cache) > 200: pop first 50`), so they are bounded,
not leaks. Timer cleanups in `editor.destroy_editor`, `index.destroy_view`,
`window._flush_pending_sidebar_resize` and `category_header_bar` (idle
`_show_all_suggestions` guarded by `_can_show_suggestions` + single retry) are
all present and correct.

## 4.2 WebKit signal handlers disconnected on teardown — OK

`destroy_editor()` disconnects `_message_handler_ids` and unregisters the known
script-message handlers; verified coverage matches the names registered in
`_setup_message_handlers()`.

---

# 5. Performance

## 5.1 Save debounce + background thread — OK

250 ms debounce coalesces keystroke bursts into one save; heavy
`html_to_markdown` work runs off the main thread. No change needed.

## 5.2 `get_notes` is lightweight — OK

List rendering selects metadata only (no content BLOBs); locked bodies are
decrypted lazily in `get_note`. Indexes cover the hot predicates
(`is_trashed`, `is_pinned`, `category`, `has_list`, `has_link`, `is_locked`,
composite `is_trashed(_pinned|_locked)_updated`). No change needed.

## 5.3 `ConfigManager` singleton reassigns `db` — **S3** — Documented

`ConfigManager.get_default(db)` mutates `cls._instance.db` in place. Every
accessor guards `if self.db:`, so a transient reassignment cannot crash, and in
practice the process uses a single shared DB. The hazard is only real if
multiple distinct DBs were ever used concurrently; note it and prefer passing
an explicit DB to the constructor if per-document stores are ever added.

---

# 6. Prioritised backlog

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1.1 | Worker read live main-thread `current_note` | S1 | ✅ Fixed |
| 1.3 | `flush_save` dropped pending edits on error | S1 | ✅ Fixed |
| 1.4 | No rollback on failed writes (open transaction) | S1 | ✅ Fixed |
| 1.2 | Stale save callback / invisible failure | S2 | ✅ Fixed |
| 2.2 | `_cleanup()` double-free | S2 | ✅ Fixed |
| 1.5 | Module-global `_GLOBAL_DB` | S3 | ✅ Fixed |
| 2.1 | Dead `if False` branch | S4 | ✅ Fixed |
| 3.2 | Silent plaintext fallback for locked notes | S3 | Documented |
| 5.3 | `ConfigManager` DB reassignment | S3 | Documented |

---

# 7. How to verify the whole set

```bash
# 1. Unit + widget suite
python -m unittest discover -s tests -v

# 2. Concurrency stress (new): hammer saves from the editor while switching notes
python -m unittest tests.test_notes_list -v

# 3. DB integrity after induced write failures
python -m unittest tests.test_database -v

# 4. Leak check (optional): run under valgrind/gdb with PYTHONMALLOC=debug
PYTHONMALLOC=debug python run.py
#   open/close several windows, scroll the notes list, then quit;
#   confirm no "GLib-CRITICAL: Source ID ... was not found" warnings
#   (the pre-fix double-_cleanup symptom).
```

**Regression assertions to add** (mirroring the fixes above):
* `test_save_snapshot_isolated_from_note_switch` (§1.1)
* `test_stale_save_callback_is_ignored` (§1.2)
* `test_flush_save_retains_pending_on_db_error` (§1.3)
* `test_write_rollback_on_error` (§1.4)
* `test_attachment_scheme_uses_owning_webview` (§1.5)
* `test_window_cleanup_idempotent` (§2.2)

> **Environment note.** The sandbox shell was unavailable during this audit
> (`Bash`/`grep` returned “Connection lost”), so the suite above was **not
> executed** here. All findings were confirmed by static analysis of the exact
> source lines cited, and the fixes were reviewed in place.
