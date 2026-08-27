from __future__ import annotations

import gettext
import os
import sys
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from . import __version__
from .adapters import AdapterRegistry, PackageAdapter
from .models import (
    InstallOptions,
    InstallScope,
    PackageKind,
    PackageMetadata,
    ProgressEvent,
)
from .transactions import TransactionLog

APP_ID = "io.github.packport.PackPort"
DOMAIN = "packport"
LOCALE_DIR = os.environ.get("PACKPORT_LOCALEDIR", "/usr/share/locale")
gettext.bindtextdomain(DOMAIN, LOCALE_DIR)
gettext.textdomain(DOMAIN)
_ = gettext.gettext


@dataclass
class QueueEntry:
    path: Path
    row: Adw.ActionRow
    status: Gtk.Label
    metadata: PackageMetadata | None = None
    adapter: PackageAdapter | None = None


class PackPortWindow(Adw.ApplicationWindow):
    def __init__(self, application: Adw.Application) -> None:
        super().__init__(application=application, title="PackPort")
        self.set_default_size(760, 700)
        self.registry = AdapterRegistry()
        self.queue: list[QueueEntry] = []
        self.current: QueueEntry | None = None
        self.cancel_event = threading.Event()
        self.current_log_path: Path | None = None
        self._indeterminate = False
        self._build_ui()
        GLib.timeout_add(150, self._pulse_progress)

    def _build_ui(self) -> None:
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        title = Adw.WindowTitle(title="PackPort", subtitle=_("Fedora package installer"))
        header.set_title_widget(title)
        about_button = Gtk.Button(icon_name="help-about-symbolic", tooltip_text=_("About PackPort"))
        about_button.connect("clicked", self._show_about)
        header.pack_end(about_button)
        toolbar.add_top_bar(header)

        page = Adw.Clamp(maximum_size=680, tightening_threshold=560)
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        main_box.set_margin_top(22)
        main_box.set_margin_bottom(22)
        main_box.set_margin_start(18)
        main_box.set_margin_end(18)
        page.set_child(main_box)
        toolbar.set_content(page)
        self.set_content(toolbar)

        self.drop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.drop_box.add_css_class("card")
        self.drop_box.set_margin_bottom(4)
        self.drop_box.set_size_request(-1, 210)
        self.drop_box.set_valign(Gtk.Align.CENTER)
        icon = Gtk.Image.new_from_icon_name("package-x-generic-symbolic")
        icon.set_pixel_size(56)
        icon.add_css_class("accent")
        heading = Gtk.Label(label=_("Drop packages here"))
        heading.add_css_class("title-2")
        detail = Gtk.Label(label=_("RPM, DEB, AppImage, Flatpak bundle or Flatpak reference"))
        detail.add_css_class("dim-label")
        detail.set_wrap(True)
        choose = Gtk.Button(label=_("Choose Files…"))
        choose.add_css_class("suggested-action")
        choose.set_halign(Gtk.Align.CENTER)
        choose.connect("clicked", self._choose_files)
        for widget in (icon, heading, detail, choose):
            self.drop_box.append(widget)
        main_box.append(self.drop_box)

        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("enter", self._drop_enter)
        drop_target.connect("leave", self._drop_leave)
        drop_target.connect("drop", self._drop_files)
        self.drop_box.add_controller(drop_target)

        queue_heading = Gtk.Label(label=_("Installation queue"), xalign=0)
        queue_heading.add_css_class("heading")
        main_box.append(queue_heading)
        self.queue_group = Adw.PreferencesGroup()
        self.empty_row = Adw.ActionRow(title=_("No packages queued"), subtitle=_("Drop one or more files to begin."))
        self.queue_group.add(self.empty_row)
        main_box.append(self.queue_group)

        progress_group = Adw.PreferencesGroup(title=_("Current transaction"))
        progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        progress_box.set_margin_top(10)
        progress_box.set_margin_bottom(10)
        progress_box.set_margin_start(12)
        progress_box.set_margin_end(12)
        self.progress_label = Gtk.Label(label=_("Waiting"), xalign=0)
        self.progress_label.set_ellipsize(3)
        self.progress_bar = Gtk.ProgressBar(show_text=False)
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.cancel_button = Gtk.Button(label=_("Cancel"))
        self.cancel_button.set_sensitive(False)
        self.cancel_button.connect("clicked", self._cancel)
        self.log_button = Gtk.ToggleButton(label=_("Show Log"))
        self.log_button.connect("toggled", self._toggle_log)
        self.export_button = Gtk.Button(label=_("Export Log…"))
        self.export_button.set_sensitive(False)
        self.export_button.connect("clicked", self._export_log)
        action_box.append(self.cancel_button)
        action_box.append(self.log_button)
        action_box.append(self.export_button)
        progress_box.append(self.progress_label)
        progress_box.append(self.progress_bar)
        progress_box.append(action_box)
        progress_group.add(progress_box)
        main_box.append(progress_group)

        self.log_revealer = Gtk.Revealer(reveal_child=False)
        scroller = Gtk.ScrolledWindow(min_content_height=150, vexpand=True)
        self.log_view = Gtk.TextView(editable=False, cursor_visible=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        scroller.set_child(self.log_view)
        self.log_revealer.set_child(scroller)
        main_box.append(self.log_revealer)

    def _show_about(self, _button: Gtk.Button) -> None:
        dialog = Adw.AboutDialog(
            application_name="PackPort",
            application_icon=APP_ID,
            version=__version__,
            developer_name="PackPort contributors",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/packport/PackPort",
            comments=_("A safe drag-and-drop package installer for Fedora."),
        )
        dialog.present(self)

    def _choose_files(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileDialog(title=_("Choose packages"), modal=True)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        supported = Gtk.FileFilter(name=_("Supported packages"))
        for pattern in ("*.rpm", "*.deb", "*.AppImage", "*.appimage", "*.flatpak", "*.flatpakref"):
            supported.add_pattern(pattern)
        filters.append(supported)
        dialog.set_filters(filters)
        dialog.open_multiple(self, None, self._files_chosen)

    def _files_chosen(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            files = dialog.open_multiple_finish(result)
        except GLib.Error:
            return
        self.enqueue_paths([files.get_item(index).get_path() for index in range(files.get_n_items())])

    def _drop_enter(self, *_args) -> Gdk.DragAction:
        self.drop_box.add_css_class("accent")
        return Gdk.DragAction.COPY

    def _drop_leave(self, *_args) -> None:
        self.drop_box.remove_css_class("accent")

    def _drop_files(self, _target, value: Gdk.FileList, _x: float, _y: float) -> bool:
        self.drop_box.remove_css_class("accent")
        paths = [item.get_path() for item in value.get_files() if item.get_path()]
        self.enqueue_paths(paths)
        return bool(paths)

    def enqueue_paths(self, paths: list[str | None]) -> None:
        for value in paths:
            if not value:
                continue
            path = Path(value)
            row = Adw.ActionRow(title=path.name, subtitle=str(path))
            status = Gtk.Label(label=_("Queued"))
            status.add_css_class("dim-label")
            row.add_suffix(status)
            self.queue_group.add(row)
            self.queue.append(QueueEntry(path, row, status))
        if self.queue and self.empty_row.get_parent():
            self.queue_group.remove(self.empty_row)
        self._process_next()

    def _process_next(self) -> None:
        if self.current is not None:
            return
        entry = next((item for item in self.queue if item.metadata is None and item.status.get_text() == _("Queued")), None)
        if entry is None:
            return
        self.current = entry
        entry.status.set_text(_("Inspecting…"))
        self.progress_label.set_text(_("Inspecting {}…").format(entry.path.name))
        self._append_log(_("Inspecting {}").format(entry.path))
        threading.Thread(target=self._inspect_worker, args=(entry,), daemon=True).start()

    def _inspect_worker(self, entry: QueueEntry) -> None:
        try:
            adapter, path = self.registry.for_path(entry.path)
            metadata = adapter.inspect(path)
            GLib.idle_add(self._inspection_done, entry, adapter, metadata, None)
        except Exception as exc:
            GLib.idle_add(self._inspection_done, entry, None, None, exc)

    def _inspection_done(self, entry, adapter, metadata, error) -> bool:
        if error:
            entry.status.set_text(_("Unsupported or invalid"))
            self._append_log(f"ERROR: {error}")
            self._show_error(_("Cannot inspect package"), str(error))
            self.current = None
            self._process_next()
            return GLib.SOURCE_REMOVE
        entry.adapter = adapter
        entry.metadata = metadata
        entry.status.set_text(_("Awaiting confirmation"))
        self._show_confirmation(entry)
        return GLib.SOURCE_REMOVE

    def _show_confirmation(self, entry: QueueEntry) -> None:
        assert entry.metadata is not None
        meta = entry.metadata
        body = _("Review the package before installation. PackPort will never bypass dependency checks.")
        dialog = Adw.AlertDialog(heading=_("Install {}?").format(meta.name), body=body)
        dialog.add_response("cancel", _("Skip"))
        dialog.add_response("install", _("Install"))
        dialog.set_response_appearance("install", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("install")
        dialog.set_close_response("cancel")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(8)
        facts = [
            (_("Format"), meta.kind.value),
            (_("Version"), meta.version),
            (_("Architecture"), meta.architecture),
            (_("Signature"), meta.signature),
            (_("SHA-256"), meta.checksum),
            (_("Source"), str(meta.path)),
        ]
        for label, value in facts:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            key = Gtk.Label(label=label, xalign=0)
            key.add_css_class("dim-label")
            key.set_size_request(100, -1)
            val = Gtk.Label(label=value, xalign=0, selectable=True, hexpand=True, wrap=True)
            row.append(key)
            row.append(val)
            box.append(row)
        if meta.warnings:
            warning = Gtk.Label(label="⚠ " + "\n⚠ ".join(meta.warnings), xalign=0, wrap=True)
            warning.add_css_class("warning")
            box.append(warning)

        scope_dropdown = None
        if meta.kind in (PackageKind.APPIMAGE, PackageKind.FLATPAK, PackageKind.FLATPAKREF):
            scope_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            scope_box.append(Gtk.Label(label=_("Install scope"), xalign=0, hexpand=True))
            scope_dropdown = Gtk.DropDown.new_from_strings([_("Current user"), _("All users")])
            scope_box.append(scope_dropdown)
            box.append(scope_box)
        scripts_check = None
        if meta.kind is PackageKind.DEB:
            scripts_check = Gtk.CheckButton(label=_("Include Debian maintainer scripts (high risk)"))
            box.append(scripts_check)
        dialog.set_extra_child(box)

        def response(_dialog: Adw.AlertDialog, response_id: str) -> None:
            if response_id != "install":
                entry.status.set_text(_("Skipped"))
                self.current = None
                self._process_next()
                return
            scope = InstallScope.USER
            if scope_dropdown is not None and scope_dropdown.get_selected() == 1:
                scope = InstallScope.SYSTEM
            options = InstallOptions(scope, bool(scripts_check and scripts_check.get_active()))
            if options.include_maintainer_scripts:
                self._confirm_scripts(entry, options)
            else:
                self._start_install(entry, options)

        dialog.connect("response", response)
        dialog.present(self)

    def _confirm_scripts(self, entry: QueueEntry, options: InstallOptions) -> None:
        dialog = Adw.AlertDialog(
            heading=_("Run Debian maintainer scripts?"),
            body=_("These scripts were written for Debian and may modify the system as administrator. Continue only if you trust the package publisher."),
        )
        dialog.add_response("back", _("Go Back"))
        dialog.add_response("continue", _("Run Scripts and Install"))
        dialog.set_response_appearance("continue", Adw.ResponseAppearance.DESTRUCTIVE)

        def response(_dialog, response_id: str) -> None:
            if response_id == "continue":
                self._start_install(entry, options)
            else:
                entry.status.set_text(_("Awaiting confirmation"))
                self._show_confirmation(entry)

        dialog.connect("response", response)
        dialog.present(self)

    def _start_install(self, entry: QueueEntry, options: InstallOptions) -> None:
        assert entry.adapter is not None and entry.metadata is not None
        self.cancel_event = threading.Event()
        entry.status.set_text(_("Installing…"))
        self.progress_bar.set_fraction(0)
        self.cancel_button.set_sensitive(True)
        self._append_log(_("Starting installation of {}" ).format(entry.metadata.name))
        threading.Thread(target=self._install_worker, args=(entry, options), daemon=True).start()

    def _install_worker(self, entry: QueueEntry, options: InstallOptions) -> None:
        transaction = None
        try:
            transaction = TransactionLog()
            GLib.idle_add(self._set_log_path, transaction.path)
            assert entry.adapter is not None and entry.metadata is not None
            plan = entry.adapter.build_plan(entry.metadata, options)
            transaction.write("plan", kind=entry.metadata.kind.value, steps=plan.steps, warnings=plan.warnings)
            result = entry.adapter.install(plan, self._emit_progress, self.cancel_event, transaction)
            verification = entry.adapter.verify(result)
            transaction.write("verification", success=verification.success, message=verification.message)
            if not verification.success:
                raise RuntimeError(verification.message)
            GLib.idle_add(self._install_done, entry, result, None)
        except Exception as exc:
            if transaction:
                transaction.write("failure", error=str(exc), traceback=traceback.format_exc(limit=8))
            GLib.idle_add(self._install_done, entry, None, exc)

    def _emit_progress(self, event: ProgressEvent) -> None:
        GLib.idle_add(self._update_progress, event)

    def _update_progress(self, event: ProgressEvent) -> bool:
        self.progress_label.set_text(event.message or event.stage)
        self.cancel_button.set_sensitive(event.cancelable)
        self._indeterminate = event.fraction is None
        if event.fraction is not None:
            self.progress_bar.set_fraction(max(0.0, min(event.fraction, 1.0)))
        self._append_log(f"[{event.stage}] {event.message}")
        return GLib.SOURCE_REMOVE

    def _pulse_progress(self) -> bool:
        if self._indeterminate:
            self.progress_bar.pulse()
        return GLib.SOURCE_CONTINUE

    def _install_done(self, entry: QueueEntry, result, error) -> bool:
        self._indeterminate = False
        self.cancel_button.set_sensitive(False)
        if error:
            entry.status.set_text(_("Failed"))
            self.progress_label.set_text(_("Installation failed"))
            self._append_log(f"ERROR: {error}")
            self._show_error(_("Installation failed"), str(error))
        else:
            entry.status.set_text(_("Installed"))
            self.progress_bar.set_fraction(1)
            self.progress_label.set_text(result.message)
            self._append_log(f"SUCCESS: {result.message}\nLog: {result.log_path}")
        self.current = None
        self._process_next()
        return GLib.SOURCE_REMOVE

    def _cancel(self, _button: Gtk.Button) -> None:
        self.cancel_event.set()
        self.cancel_button.set_sensitive(False)
        self.progress_label.set_text(_("Cancelling…"))

    def _toggle_log(self, button: Gtk.ToggleButton) -> None:
        shown = button.get_active()
        self.log_revealer.set_reveal_child(shown)
        button.set_label(_("Hide Log") if shown else _("Show Log"))

    def _set_log_path(self, path: Path) -> bool:
        self.current_log_path = path
        self.export_button.set_sensitive(True)
        return GLib.SOURCE_REMOVE

    def _export_log(self, _button: Gtk.Button) -> None:
        if self.current_log_path is None:
            return
        dialog = Gtk.FileDialog(title=_("Export transaction log"), modal=True)
        dialog.set_initial_name(self.current_log_path.name)
        dialog.save(self, None, self._log_destination_chosen)

    def _log_destination_chosen(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            destination = dialog.save_finish(result)
            assert self.current_log_path is not None
            source = Gio.File.new_for_path(str(self.current_log_path))
            source.copy(destination, Gio.FileCopyFlags.OVERWRITE, None, None, None)
        except GLib.Error as exc:
            if not exc.matches(Gtk.DialogError.quark(), Gtk.DialogError.DISMISSED):
                self._show_error(_("Could not export log"), exc.message)

    def _append_log(self, text: str) -> None:
        buffer = self.log_view.get_buffer()
        end = buffer.get_end_iter()
        buffer.insert(end, text.rstrip() + "\n")

    def _show_error(self, heading: str, message: str) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=message)
        dialog.add_response("close", _("Close"))
        dialog.present(self)


class PackPortApplication(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.window: PackPortWindow | None = None

    def do_activate(self) -> None:
        if self.window is None:
            self.window = PackPortWindow(self)
        self.window.present()

    def do_open(self, files: list[Gio.File], _n_files: int, _hint: str) -> None:
        self.do_activate()
        assert self.window is not None
        self.window.enqueue_paths([item.get_path() for item in files])


def main(argv: list[str] | None = None) -> int:
    app = PackPortApplication()
    return app.run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
