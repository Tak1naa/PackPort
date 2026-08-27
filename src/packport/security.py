from __future__ import annotations

import hashlib
import os
import platform
import re
from pathlib import Path

from .models import PackageKind, PackPortError, UnsupportedPackageError

RPM_MAGIC = b"\xed\xab\xee\xdb"
AR_MAGIC = b"!<arch>\n"
ELF_MAGIC = b"\x7fELF"
ARCHIVE_SUFFIXES = (".tar", ".tar.gz", ".tar.xz", ".tar.zst", ".tgz", ".zip", ".7z")


def validate_input_path(value: str | os.PathLike[str]) -> Path:
    raw = Path(value).expanduser()
    try:
        path = raw.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PackPortError(f"Cannot access the selected file: {exc}") from exc
    if not path.is_file():
        raise PackPortError("The selected path is not a regular file.")
    try:
        if path.stat().st_size <= 0:
            raise PackPortError("The selected file is empty.")
    except OSError as exc:
        raise PackPortError(f"Cannot inspect the selected file: {exc}") from exc
    return path


def sniff_package_kind(path: Path) -> PackageKind:
    suffix = path.name.lower()
    try:
        with path.open("rb") as stream:
            header = stream.read(4096)
    except OSError as exc:
        raise PackPortError(f"Cannot read the selected file: {exc}") from exc

    if header.startswith(RPM_MAGIC):
        return PackageKind.RPM
    if header.startswith(AR_MAGIC) and (suffix.endswith(".deb") or b"debian" in header):
        return PackageKind.DEB
    if header.startswith(ELF_MAGIC) and (header[8:11] in (b"AI\x01", b"AI\x02") or suffix.endswith(".appimage")):
        return PackageKind.APPIMAGE
    if suffix.endswith(".flatpakref"):
        text = header.decode("utf-8", errors="ignore")
        if "[Flatpak Ref]" not in text:
            raise PackPortError("This .flatpakref file has no [Flatpak Ref] section.")
        return PackageKind.FLATPAKREF
    if suffix.endswith(".flatpak"):
        return PackageKind.FLATPAK
    if suffix.endswith(ARCHIVE_SUFFIXES):
        raise UnsupportedPackageError(
            "Archives do not have a standard installation contract. Extract the archive and follow its documentation."
        )
    raise UnsupportedPackageError(
        "Unsupported package format. PackPort supports RPM, DEB, AppImage, .flatpak, and .flatpakref files."
    )


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_arch(value: str) -> str:
    aliases = {
        "amd64": "x86_64",
        "x86-64": "x86_64",
        "arm64": "aarch64",
        "all": "noarch",
        "any": "noarch",
    }
    clean = value.strip().lower()
    return aliases.get(clean, clean)


def host_arch() -> str:
    return normalize_arch(platform.machine())


def architecture_warning(package_arch: str) -> str | None:
    normalized = normalize_arch(package_arch)
    if normalized in ("", "unknown", "noarch", host_arch()):
        return None
    return f"Package architecture {package_arch} does not match this system ({host_arch()})."


def safe_display_text(value: str, fallback: str = "Unknown", limit: int = 200) -> str:
    value = re.sub(r"[\x00-\x1f\x7f]", " ", value or "")
    value = " ".join(value.split()).strip()
    return value[:limit] or fallback


def safe_slug(value: str, fallback: str = "application") -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", safe_display_text(value, fallback)).strip(".-")
    return (slug or fallback)[:100]


def desktop_exec_quote(path: Path) -> str:
    # Desktop Entry Exec quoting is not shell quoting. Backslash and quote are
    # escaped inside double quotes; field-code percent signs must be doubled.
    value = str(path).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    return f'"{value}"'


def find_squashfs_offset(path: Path, scan_limit: int = 64 * 1024 * 1024) -> int | None:
    """Locate the appended SquashFS without executing the AppImage runtime."""
    overlap = b""
    position = 0
    with path.open("rb") as stream:
        while position < scan_limit:
            block = stream.read(min(1024 * 1024, scan_limit - position))
            if not block:
                return None
            data = overlap + block
            index = data.find(b"hsqs")
            if index >= 0:
                return position - len(overlap) + index
            overlap = data[-3:]
            position += len(block)
    return None

