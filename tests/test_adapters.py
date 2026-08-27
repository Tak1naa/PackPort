from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from packport.adapters import AdapterRegistry, AppImageAdapter, DebAdapter, FlatpakAdapter, RpmAdapter
from packport.models import InstallOptions, InstallScope, PackageKind, PackageMetadata, ProgressEvent
from packport.transactions import TransactionLog


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def run(self, args, **kwargs):
        self.calls.append(list(args))
        kwargs["progress"](ProgressEvent(kwargs["stage"], 1.0, "done", kwargs.get("cancelable", True)))
        kwargs["log"]("done")
        return "done"


class AdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_rpm_metadata_and_install_command(self) -> None:
        path = self.root / "sample.rpm"
        path.write_bytes(b"\xed\xab\xee\xdbpayload")
        runner = FakeRunner()
        adapter = RpmAdapter(runner)  # type: ignore[arg-type]
        with patch("packport.adapters.run_capture") as capture:
            capture.side_effect = [
                (0, "sample\n1.2-1\nnoarch\nExample package"),
                (0, f"{path}: digests signatures OK"),
            ]
            metadata = adapter.inspect(path)
        self.assertEqual(metadata.name, "sample")
        self.assertEqual(metadata.version, "1.2-1")
        plan = adapter.build_plan(metadata, InstallOptions())
        with patch.dict("os.environ", {"PACKPORT_HELPER": "/test/helper"}):
            result = adapter.install(plan, lambda _event: None, threading.Event(), TransactionLog(self.root))
        self.assertTrue(result.success)
        self.assertEqual(runner.calls[0], ["pkexec", "/test/helper", "install-rpm", str(path.resolve())])
        self.assertNotIn("--allowerasing", runner.calls[0])

    def test_deb_scripts_are_opt_in(self) -> None:
        adapter = DebAdapter(FakeRunner())  # type: ignore[arg-type]
        metadata = PackageMetadata(self.root / "sample.deb", PackageKind.DEB, "sample")
        safe_plan = adapter.build_plan(metadata, InstallOptions(InstallScope.SYSTEM, False))
        risky_plan = adapter.build_plan(metadata, InstallOptions(InstallScope.SYSTEM, True))
        self.assertFalse(safe_plan.options.include_maintainer_scripts)
        self.assertTrue(risky_plan.options.include_maintainer_scripts)
        self.assertTrue(any("administrator" in warning for warning in risky_plan.warnings))

    def test_flatpak_uses_explicit_scope_and_input_mode(self) -> None:
        path = self.root / "example.flatpakref"
        path.write_text("[Flatpak Ref]\nName=org.example.App\nUrl=https://example.invalid/repo\n", encoding="utf-8")
        runner = FakeRunner()
        adapter = FlatpakAdapter(PackageKind.FLATPAKREF, runner)  # type: ignore[arg-type]
        metadata = adapter.inspect(path)
        plan = adapter.build_plan(metadata, InstallOptions(InstallScope.USER))
        adapter.install(plan, lambda _event: None, threading.Event(), TransactionLog(self.root))
        command = runner.calls[0]
        self.assertIn("--user", command)
        self.assertIn("--from", command)
        self.assertIn("--noninteractive", command)

    def test_user_appimage_install_is_atomic_and_executable(self) -> None:
        source = self.root / "Demo.AppImage"
        source.write_bytes(b"\x7fELF" + b"\0" * 4 + b"AI\x02" + b"payload")
        adapter = AppImageAdapter(FakeRunner())  # type: ignore[arg-type]
        metadata = PackageMetadata(
            source,
            PackageKind.APPIMAGE,
            "Demo\nApplication",
            checksum="a" * 64,
            size=source.stat().st_size,
        )
        plan = adapter.build_plan(metadata, InstallOptions(InstallScope.USER))
        fake_home = self.root / "home"
        fake_home.mkdir()
        with patch("pathlib.Path.home", return_value=fake_home):
            result = adapter.install(plan, lambda _event: None, threading.Event(), TransactionLog(self.root))
        target = Path(result.installed_ref or "")
        self.assertTrue(target.is_file())
        self.assertTrue(target.stat().st_mode & 0o111)
        desktop = fake_home / ".local/share/applications/io.github.packport.AppImage.aaaaaaaaaaaaaaaa.desktop"
        self.assertTrue(desktop.is_file())
        self.assertNotIn("\nApplication\nExec=", desktop.read_text(encoding="utf-8"))

    def test_registry_rejects_unknown_input(self) -> None:
        path = self.root / "unknown.zip"
        path.write_bytes(b"PK")
        with self.assertRaises(Exception):
            AdapterRegistry(FakeRunner()).for_path(path)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()

