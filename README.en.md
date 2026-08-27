# PackPort

PackPort is a native Fedora desktop installer for local Linux packages. Drop a package onto the window, review what will happen, choose the installation scope, and follow the transaction progress without opening a terminal.

## Supported formats

- `.rpm`: installed with DNF5 after checking RPM metadata, architecture, and signature status.
- `.deb`: converted to a temporary RPM with Alien as the current user, then installed by DNF5. Debian maintainer scripts are disabled by default and require a second confirmation.
- `.AppImage`: copied into a PackPort-managed directory and integrated with the desktop menu, for the current user or the whole system.
- `.flatpak`: installed as a Flatpak bundle.
- `.flatpakref`: installed as a Flatpak reference; it may add a remote and download runtimes from the network.

Archives and unknown formats are not force-installed. DEB conversion cannot guarantee Fedora compatibility. PackPort never bypasses dependency checks with `--nodeps`, `--skip-broken`, or `--allowerasing`.

## Installation

Fedora 43 x86_64 RPM:

```sh
sudo dnf install ./dist/packport-0.1.0-1.fc43.noarch.rpm
```

Launch it from the application menu or run:

```sh
packport
```

## Features

- Full-window drag and drop with a sequential multi-file queue.
- Pre-install details including package name, version, architecture, signature, SHA-256, source path, and warnings.
- Per-install user/system scope for AppImage and Flatpak.
- Live stage or percentage progress from DNF, Alien, and Flatpak backends.
- Private transaction logs in `~/.local/state/packport/transactions/`, with log export from the UI.
- Simplified Chinese and English translations, plus MIME/Open With associations.

## Development

Install dependencies on Fedora 43:

```sh
sudo dnf install meson ninja-build python3-gobject gtk4 libadwaita \
  gettext desktop-file-utils appstream polkit flatpak alien dpkg \
  squashfs-tools rpm-build
```

Build, test, and install into a staging directory:

```sh
meson setup build
meson compile -C build
meson test -C build --print-errorlogs
meson install -C build --destdir "$PWD/stage"
```

Run directly from the source tree:

```sh
PYTHONPATH=src python3 -m packport.application
```

## Security model

The graphical process remains unprivileged. RPM installation and system-wide AppImage integration go through a restricted Polkit helper with fixed subcommands; it does not accept arbitrary shell commands.

Input paths are resolved and validated as regular files, and all external commands use argument arrays. Package inspection never executes the input file. AppImage integration uses temporary files and atomic renames.

Cancellation is disabled once DNF enters the transaction commit phase, avoiding damage to the RPM database. Failed operations retain diagnostics without claiming a rollback that did not occur.

## Project and license

PackPort is licensed under GPL-3.0-or-later. The AppImage integration design was informed by [Gear Lever](https://github.com/mijorus/gearlever); attribution and license information are in [`NOTICE`](NOTICE).

PackPort currently does not provide an app store, online search, update management, Snap support, or installation of generic archives.

