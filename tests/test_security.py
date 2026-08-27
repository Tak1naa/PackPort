from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from packport.models import PackageKind, PackPortError, UnsupportedPackageError
from packport.security import (
    architecture_warning,
    desktop_exec_quote,
    find_squashfs_offset,
    safe_display_text,
    safe_slug,
    sha256_file,
    sniff_package_kind,
    validate_input_path,
)


class SecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, name: str, data: bytes) -> Path:
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_detects_supported_formats_from_content_and_name(self) -> None:
        rpm = self.write("renamed.bin", b"\xed\xab\xee\xdb" + b"x" * 32)
        deb = self.write("sample.deb", b"!<arch>\ndebian-binary   " + b"x" * 32)
        appimage = self.write("sample.AppImage", b"\x7fELF" + b"\0" * 4 + b"AI\x02" + b"x" * 32)
        ref = self.write("sample.flatpakref", b"[Flatpak Ref]\nName=org.example.App\n")
        bundle = self.write("sample.flatpak", b"not-empty")
        self.assertEqual(sniff_package_kind(rpm), PackageKind.RPM)
        self.assertEqual(sniff_package_kind(deb), PackageKind.DEB)
        self.assertEqual(sniff_package_kind(appimage), PackageKind.APPIMAGE)
        self.assertEqual(sniff_package_kind(ref), PackageKind.FLATPAKREF)
        self.assertEqual(sniff_package_kind(bundle), PackageKind.FLATPAK)

    def test_rejects_archives_and_unknown_files(self) -> None:
        with self.assertRaises(UnsupportedPackageError):
            sniff_package_kind(self.write("source.tar.gz", b"archive"))
        with self.assertRaises(UnsupportedPackageError):
            sniff_package_kind(self.write("program.exe", b"MZ"))

    def test_rejects_empty_and_directory_inputs(self) -> None:
        with self.assertRaises(PackPortError):
            validate_input_path(self.write("empty.rpm", b""))
        with self.assertRaises(PackPortError):
            validate_input_path(self.root)

    def test_resolves_symlink_to_regular_file(self) -> None:
        target = self.write("target.rpm", b"data")
        link = self.root / "link.rpm"
        link.symlink_to(target)
        self.assertEqual(validate_input_path(link), target)

    def test_sanitizes_desktop_values(self) -> None:
        self.assertEqual(safe_display_text("Good\nName\x00Exec=bad"), "Good Name Exec=bad")
        self.assertEqual(safe_slug("../ Bad / Name"), "Bad-Name")
        quoted = desktop_exec_quote(Path('/tmp/a "quoted" %F.AppImage'))
        self.assertEqual(quoted, '"/tmp/a \\"quoted\\" %%F.AppImage"')

    def test_hash_and_appimage_offset(self) -> None:
        path = self.write("offset.AppImage", b"\x7fELF" + b"x" * 64 + b"hsqs" + b"rest")
        self.assertEqual(find_squashfs_offset(path), 68)
        self.assertEqual(len(sha256_file(path)), 64)

    def test_architecture_warning(self) -> None:
        self.assertIsNone(architecture_warning("noarch"))
        self.assertIsNone(architecture_warning(os.uname().machine))
        self.assertIsNotNone(architecture_warning("definitely-another-arch"))


if __name__ == "__main__":
    unittest.main()

