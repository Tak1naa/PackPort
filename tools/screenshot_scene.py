#!/usr/bin/python3
"""Render deterministic PackPort UI states for project screenshots.

This helper never installs a package. It presents the real application widgets
with sample metadata so maintainers can capture documentation images safely.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from packport.application import PackPortApplication, QueueEntry
from packport.models import InstallOptions, InstallScope, PackageKind, PackageMetadata


class ScreenshotApplication(PackPortApplication):
    def __init__(self, scene: str) -> None:
        super().__init__()
        self.scene = scene

    def do_activate(self) -> None:
        super().do_activate()
        GLib.timeout_add(350, self._show_scene)

    def _entry(self, filename: str, status_text: str) -> QueueEntry:
        assert self.window is not None
        path = Path("/home/demo/Downloads") / filename
        row = Adw.ActionRow(title=filename, subtitle=str(path))
        status = Gtk.Label(label=status_text)
        status.add_css_class("dim-label")
        row.add_suffix(status)
        if self.window.empty_row.get_parent():
            self.window.queue_group.remove(self.window.empty_row)
        self.window.queue_group.add(row)
        entry = QueueEntry(path, row, status)
        self.window.queue.append(entry)
        return entry

    def _show_scene(self) -> bool:
        assert self.window is not None
        window = self.window

        if self.scene == "drag":
            window.drop_box.add_css_class("accent")
            window.progress_label.set_text("Ready — drop one or more packages above")
            return GLib.SOURCE_REMOVE

        if self.scene == "details":
            entry = self._entry("GearLever-3.1.0-x86_64.AppImage", "Awaiting confirmation")
            entry.metadata = PackageMetadata(
                path=entry.path,
                kind=PackageKind.APPIMAGE,
                name="Gear Lever",
                version="3.1.0",
                architecture="x86_64",
                checksum="92012f8d7d57fb7a31bc3c956864eba63de3c87c57c7de898f3d2aa430b8d4ab",
                signature="Not provided by AppImage format",
                size=18_874_368,
                warnings=["AppImage files are executable applications. Install only from a trusted publisher."],
            )
            window.current = entry
            window._show_confirmation(entry)
            return GLib.SOURCE_REMOVE

        if self.scene == "permission":
            entry = self._entry("example-editor_2.4.1_amd64.deb", "High-risk confirmation")
            entry.metadata = PackageMetadata(
                path=entry.path,
                kind=PackageKind.DEB,
                name="Example Editor",
                version="2.4.1",
                architecture="amd64",
            )
            window.current = entry
            window._confirm_scripts(entry, InstallOptions(InstallScope.SYSTEM, True))
            return GLib.SOURCE_REMOVE

        entry = self._entry("demo-app-1.4.2-1.x86_64.rpm", "Installing…")
        entry.metadata = PackageMetadata(
            path=entry.path,
            kind=PackageKind.RPM,
            name="Demo App",
            version="1.4.2-1",
            architecture="x86_64",
        )
        window.current = entry
        window.progress_label.set_text("Installing Demo App — 68%")
        window.progress_bar.set_fraction(0.68)
        window.cancel_button.set_sensitive(False)
        window.log_button.set_active(True)
        for line in (
            "[Inspecting] RPM metadata and signature checked",
            "[Resolving] Dependencies resolved with DNF5",
            "[Installing] Running transaction — 68%",
            "[Installing] Cancellation disabled during RPM commit",
        ):
            window._append_log(line)
        return GLib.SOURCE_REMOVE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scene", choices=("drag", "details", "permission", "progress"))
    args = parser.parse_args(argv)
    return ScreenshotApplication(args.scene).run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
