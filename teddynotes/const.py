# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import sys
from pathlib import Path

APP_ID = "io.github.fastrizwaan.TeddyNotes"
APP_NAME = "Teddy Notes"
VERSION = "1.6"
PROFILE = ""
IS_DEVEL = False
PKGDATADIR = "/usr/share/teddynotes"
LOCALEDIR = "/usr/share/locale"

def get_assets_path() -> Path:
    """Find the assets directory either from installed location or dev source."""
    # 1. Dev directory relative to source root
    dev_path = Path(__file__).resolve().parent.parent / "assets"
    if dev_path.exists():
        return dev_path

    # 2. Installed package data directory
    pkg_path = Path(PKGDATADIR) / "assets"
    if pkg_path.exists():
        return pkg_path

    # 3. Fallback to /app or system share
    for prefix in [
        "/app/share/teddynotes/assets",
        "/usr/share/teddynotes/assets",
        "/usr/local/share/teddynotes/assets",
        "/app/share/stilonotes/assets",
        "/usr/share/stilonotes/assets",
        "/usr/local/share/stilonotes/assets",
    ]:
        p = Path(prefix)
        if p.exists():
            return p

    return dev_path
