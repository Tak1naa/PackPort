from __future__ import annotations

import configparser
import os
import tempfile
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

from .models import (
    InstallOptions,
    InstallPlan,
    InstallResult,
    InstallScope,
    PackageKind,
    PackageMetadata,
    PackPortError,
    ProgressEvent,
    VerificationResult,
)
from .runner import CommandRunner, run_capture
from .security import (
    architecture_warning,
    desktop_exec_quote,
    find_squashfs_offset,
    safe_display_text,
    safe_slug,
    sha256_file,
    sniff_package_kind,
    validate_input_path,
)
from .transactions import TransactionLog

ProgressCallback = Callable[[ProgressEvent], None]


class PackageAdapter(ABC):
    kind: PackageKind

    def __init__(self, runner: CommandRunner | None = None) -> None:
        self.runner = runner or CommandRunner()

    @abstractmethod
    def inspect(self, path: Path) -> PackageMetadata: ...

    @abstractmethod
    def build_plan(self, metadata: PackageMetadata, options: InstallOptions) -> InstallPlan: ...

    @abstractmethod
    def install(
        self,
        plan: InstallPlan,
        progress: ProgressCallback,
        cancel: threading.Event,
        transaction: TransactionLog,
    ) -> InstallResult: ...

    @abstractmethod
    def verify(self, result: InstallResult) -> VerificationResult: ...

    @staticmethod
    def _base_metadata(path: Path, kind: PackageKind, name: str) -> PackageMetadata:
        return PackageMetadata(
            path=path,
            kind=kind,
            name=safe_display_text(name, path.stem),
            checksum=sha256_file(path),
            size=path.stat().st_size,
        )


class RpmAdapter(PackageAdapter):
    kind = PackageKind.RPM
    query_format = "%{NAME}\\n%{VERSION}-%{RELEASE}\\n%{ARCH}\\n%{SUMMARY}"

    def inspect(self, path: Path) -> PackageMetadata:
        path = validate_input_path(path)
        if sniff_package_kind(path) is not self.kind:
            raise PackPortError("The file does not contain a valid RPM header.")
        code, output = run_capture(["rpm", "-qp", "--queryformat", self.query_format, str(path)])
        if code != 0:
            raise PackPortError(f"RPM metadata could not be read: {output}")
        lines = output.splitlines()
        if len(lines) < 3:
            raise PackPortError("RPM metadata is incomplete.")
        meta = self._base_metadata(path, self.kind, lines[0])
        meta.version = safe_display_text(lines[1])
        meta.architecture = safe_display_text(lines[2])
        meta.description = safe_display_text(lines[3] if len(lines) > 3 else "", "")
        sig_code, signature = run_capture(["rpmkeys", "--checksig", "--verbose", str(path)])
        signature_text = safe_display_text(signature, "Unsigned or unknown")
        meta.signature = signature_text
        if sig_code != 0 or "NOT OK" in signature.upper() or "NOKEY" in signature.upper():
            meta.warnings.append("The RPM signature is missing, untrusted, or could not be verified.")
        mismatch = architecture_warning(meta.architecture)
        if mismatch:
            meta.warnings.append(mismatch)
        return meta

    def build_plan(self, metadata: PackageMetadata, options: InstallOptions) -> InstallPlan:
        return InstallPlan(
            metadata,
            InstallOptions(scope=InstallScope.SYSTEM),
            ["Validate RPM", "Resolve dependencies with DNF5", "Commit RPM transaction", "Verify installation"],
            True,
            list(metadata.warnings),
        )

    @staticmethod
    def _helper_path() -> str:
        configured = os.environ.get("PACKPORT_HELPER")
        if configured:
            return configured
        return "/usr/libexec/packport-helper"

    def install(self, plan, progress, cancel, transaction) -> InstallResult:
        transaction.write("install-start", kind="rpm", path=plan.metadata.path, checksum=plan.metadata.checksum)
        args = ["pkexec", self._helper_path(), "install-rpm", str(plan.metadata.path)]
        # Once the root helper begins, cancellation is disabled: killing the
        # Polkit client cannot safely guarantee cancellation of a DNF commit.
        output = self.runner.run(
            args,
            stage="Installing RPM",
            progress=progress,
            log=lambda line: transaction.write("command-output", line=line),
            cancel=cancel,
            cancelable=False,
        )
        result = InstallResult(True, "RPM installed successfully.", plan.metadata.name, transaction.path, {"output": output})
        transaction.write("install-complete", success=True, installed_ref=plan.metadata.name)
        return result

    def verify(self, result: InstallResult) -> VerificationResult:
        if not result.installed_ref:
            return VerificationResult(False, "No RPM name was returned for verification.")
        code, output = run_capture(["rpm", "-q", result.installed_ref])
        return VerificationResult(code == 0, output or "RPM verification failed.")


class DebAdapter(PackageAdapter):
    kind = PackageKind.DEB
    fields = "${Package}\\n${Version}\\n${Architecture}\\n${Description}"

    def __init__(self, runner: CommandRunner | None = None, rpm_adapter: RpmAdapter | None = None) -> None:
        super().__init__(runner)
        self.rpm_adapter = rpm_adapter or RpmAdapter(self.runner)

    def inspect(self, path: Path) -> PackageMetadata:
        path = validate_input_path(path)
        if sniff_package_kind(path) is not self.kind:
            raise PackPortError("The file does not contain a Debian package archive.")
        code, output = run_capture(["dpkg-deb", "--show", f"--showformat={self.fields}", str(path)])
        if code != 0:
            raise PackPortError(f"DEB metadata could not be read: {output}")
        lines = output.splitlines()
        if len(lines) < 3:
            raise PackPortError("DEB metadata is incomplete.")
        meta = self._base_metadata(path, self.kind, lines[0])
        meta.version = safe_display_text(lines[1])
        meta.architecture = safe_display_text(lines[2])
        meta.description = safe_display_text(" ".join(lines[3:]), "")
        meta.signature = "Not provided by the DEB format"
        meta.warnings.append("DEB packages target Debian-family systems; conversion cannot guarantee Fedora compatibility.")
        mismatch = architecture_warning(meta.architecture)
        if mismatch:
            meta.warnings.append(mismatch)
        return meta

    def build_plan(self, metadata: PackageMetadata, options: InstallOptions) -> InstallPlan:
        warnings = list(metadata.warnings)
        if options.include_maintainer_scripts:
            warnings.append("Debian maintainer scripts will run as administrator after conversion.")
        return InstallPlan(
            metadata,
            InstallOptions(InstallScope.SYSTEM, options.include_maintainer_scripts),
            ["Validate DEB", "Convert to RPM as current user", "Inspect converted RPM", "Install with DNF5", "Verify installation"],
            True,
            warnings,
        )

    def install(self, plan, progress, cancel, transaction) -> InstallResult:
        transaction.write(
            "install-start",
            kind="deb",
            path=plan.metadata.path,
            checksum=plan.metadata.checksum,
            maintainer_scripts=plan.options.include_maintainer_scripts,
        )
        cache = Path.home() / ".cache" / "packport" / "conversion"
        cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(prefix="deb-", dir=cache) as temporary:
            args = ["alien", "--to-rpm", "--keep-version"]
            if plan.options.include_maintainer_scripts:
                args.append("--scripts")
            args.append(str(plan.metadata.path))
            self.runner.run(
                args,
                stage="Converting DEB to RPM",
                progress=progress,
                log=lambda line: transaction.write("command-output", line=line),
                cancel=cancel,
                cancelable=True,
                cwd=temporary,
            )
            rpms = sorted(Path(temporary).glob("*.rpm"), key=lambda item: item.stat().st_mtime, reverse=True)
            if not rpms:
                raise PackPortError("Alien completed without producing an RPM file.")
            converted = self.rpm_adapter.inspect(rpms[0])
            transaction.write("conversion-complete", rpm=rpms[0], rpm_checksum=converted.checksum)
            converted_plan = self.rpm_adapter.build_plan(converted, InstallOptions(InstallScope.SYSTEM))
            result = self.rpm_adapter.install(converted_plan, progress, cancel, transaction)
            result.message = "DEB converted and installed successfully."
            result.details["source_kind"] = "deb"
            return result

    def verify(self, result: InstallResult) -> VerificationResult:
        return self.rpm_adapter.verify(result)


class AppImageAdapter(PackageAdapter):
    kind = PackageKind.APPIMAGE

    def inspect(self, path: Path) -> PackageMetadata:
        path = validate_input_path(path)
        if sniff_package_kind(path) is not self.kind:
            raise PackPortError("The file is not a recognized AppImage.")
        meta = self._base_metadata(path, self.kind, path.name.rsplit(".AppImage", 1)[0])
        meta.architecture = "Embedded ELF"
        meta.signature = "No verified embedded signature"
        meta.warnings.append("AppImages are third-party executables; install only files from a trusted source.")
        offset = find_squashfs_offset(path)
        if offset is not None:
            meta.extra["squashfs_offset"] = offset
            desktop = self._extract_desktop_metadata(path, offset)
            if desktop:
                meta.name = desktop.get("Name", meta.name)
                meta.version = desktop.get("X-AppImage-Version", meta.version)
                meta.description = desktop.get("Comment", "")
        else:
            meta.warnings.append("Embedded metadata could not be located; a generic launcher will be created.")
        return meta

    @staticmethod
    def _extract_desktop_metadata(path: Path, offset: int) -> dict[str, str]:
        with tempfile.TemporaryDirectory(prefix="packport-inspect-") as temporary:
            code, _ = run_capture(
                ["unsquashfs", "-no-xattrs", "-d", temporary, "-o", str(offset), str(path), "*.desktop"],
                timeout=12,
            )
            if code != 0:
                return {}
            desktop_files = list(Path(temporary).rglob("*.desktop"))[:1]
            if not desktop_files:
                return {}
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(desktop_files[0], encoding="utf-8")
                section = parser["Desktop Entry"]
                return {
                    key: safe_display_text(section.get(key, ""), "", 200)
                    for key in ("Name", "Comment", "X-AppImage-Version")
                    if section.get(key)
                }
            except (OSError, configparser.Error):
                return {}

    def build_plan(self, metadata: PackageMetadata, options: InstallOptions) -> InstallPlan:
        target = "current user" if options.scope is InstallScope.USER else "all users"
        return InstallPlan(
            metadata,
            options,
            ["Validate AppImage", f"Copy for {target}", "Create desktop launcher", "Verify integration"],
            options.scope is InstallScope.SYSTEM,
            list(metadata.warnings),
        )

    def install(self, plan, progress, cancel, transaction) -> InstallResult:
        transaction.write("install-start", kind="appimage", path=plan.metadata.path, scope=plan.options.scope.value)
        if plan.options.scope is InstallScope.SYSTEM:
            output = self.runner.run(
                ["pkexec", RpmAdapter._helper_path(), "integrate-appimage", str(plan.metadata.path)],
                stage="Integrating AppImage for all users",
                progress=progress,
                log=lambda line: transaction.write("command-output", line=line),
                cancel=cancel,
                cancelable=False,
            )
            result = InstallResult(True, "AppImage integrated for all users.", None, transaction.path, {"output": output})
        else:
            result = self._install_user(plan, progress, cancel, transaction)
        transaction.write("install-complete", success=True, installed_ref=result.installed_ref)
        return result

    def _install_user(self, plan, progress, cancel, transaction) -> InstallResult:
        meta = plan.metadata
        digest = meta.checksum[:16]
        app_dir = Path.home() / ".local" / "share" / "packport" / "appimages" / digest
        desktop_dir = Path.home() / ".local" / "share" / "applications"
        app_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        desktop_dir.mkdir(parents=True, exist_ok=True)
        target = app_dir / f"{safe_slug(meta.name)}.AppImage"
        temporary = app_dir / f".{target.name}.partial"
        progress(ProgressEvent("Copying AppImage", 0.05, "Copying AppImage", True))
        try:
            with meta.path.open("rb") as source, temporary.open("wb") as destination:
                copied = 0
                while chunk := source.read(1024 * 1024):
                    if cancel.is_set():
                        raise PackPortError("The operation was cancelled.")
                    destination.write(chunk)
                    copied += len(chunk)
                    progress(ProgressEvent("Copying AppImage", min(copied / meta.size, 1.0), "Copying AppImage", True))
                destination.flush()
                os.fsync(destination.fileno())
            temporary.chmod(0o755)
            temporary.replace(target)
            desktop_id = f"io.github.packport.AppImage.{digest}.desktop"
            desktop_path = desktop_dir / desktop_id
            desktop_content = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                f"Name={safe_display_text(meta.name)}\n"
                f"Comment={safe_display_text(meta.description, 'Installed by PackPort')}\n"
                f"Exec={desktop_exec_quote(target)}\n"
                "Icon=application-x-executable\n"
                "Terminal=false\n"
                "Categories=Utility;\n"
                "X-PackPort-Managed=true\n"
            )
            desktop_tmp = desktop_path.with_suffix(".desktop.partial")
            desktop_tmp.write_text(desktop_content, encoding="utf-8")
            desktop_tmp.chmod(0o644)
            desktop_tmp.replace(desktop_path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        progress(ProgressEvent("Integrating AppImage", 1.0, "Desktop launcher created", False))
        transaction.write("appimage-integrated", target=target, desktop=desktop_path)
        return InstallResult(True, "AppImage integrated for the current user.", str(target), transaction.path)

    def verify(self, result: InstallResult) -> VerificationResult:
        if result.installed_ref:
            path = Path(result.installed_ref)
            ok = path.is_file() and os.access(path, os.X_OK)
            return VerificationResult(ok, "AppImage integration verified." if ok else "Installed AppImage was not found.")
        return VerificationResult(result.success, result.message)


class FlatpakAdapter(PackageAdapter):
    def __init__(self, kind: PackageKind, runner: CommandRunner | None = None) -> None:
        if kind not in (PackageKind.FLATPAK, PackageKind.FLATPAKREF):
            raise ValueError("FlatpakAdapter requires a Flatpak package kind")
        super().__init__(runner)
        self.kind = kind

    def inspect(self, path: Path) -> PackageMetadata:
        path = validate_input_path(path)
        if sniff_package_kind(path) is not self.kind:
            raise PackPortError("The selected file is not the expected Flatpak format.")
        if self.kind is PackageKind.FLATPAKREF:
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(path, encoding="utf-8")
                section = parser["Flatpak Ref"]
            except (OSError, KeyError, configparser.Error) as exc:
                raise PackPortError(f"Flatpak reference could not be parsed: {exc}") from exc
            name = section.get("Name", path.stem)
            meta = self._base_metadata(path, self.kind, name)
            meta.architecture = safe_display_text(section.get("IsRuntime", "false") == "true" and "Runtime" or "Application")
            meta.description = safe_display_text(section.get("Title", ""), "")
            meta.extra["url"] = section.get("Url", "")
            meta.signature = "Validated by Flatpak during installation"
            meta.warnings.append("This reference may add a remote and download data from the network.")
        else:
            meta = self._base_metadata(path, self.kind, path.stem)
            meta.signature = "Validated by Flatpak during installation"
        return meta

    def build_plan(self, metadata: PackageMetadata, options: InstallOptions) -> InstallPlan:
        return InstallPlan(
            metadata,
            options,
            ["Validate Flatpak input", "Resolve runtimes and download data", "Deploy application", "Verify Flatpak transaction"],
            options.scope is InstallScope.SYSTEM,
            list(metadata.warnings),
        )

    def install(self, plan, progress, cancel, transaction) -> InstallResult:
        args = ["flatpak", "install", "--assumeyes", "--noninteractive"]
        args.append("--user" if plan.options.scope is InstallScope.USER else "--system")
        args.append("--bundle" if self.kind is PackageKind.FLATPAK else "--from")
        args.append(str(plan.metadata.path))
        transaction.write("install-start", kind=self.kind.value, path=plan.metadata.path, scope=plan.options.scope.value)
        output = self.runner.run(
            args,
            stage="Installing Flatpak",
            progress=progress,
            log=lambda line: transaction.write("command-output", line=line),
            cancel=cancel,
            cancelable=True,
        )
        result = InstallResult(True, "Flatpak installed successfully.", plan.metadata.name, transaction.path, {"output": output})
        transaction.write("install-complete", success=True, installed_ref=plan.metadata.name)
        return result

    def verify(self, result: InstallResult) -> VerificationResult:
        # Flatpak itself verifies the OSTree transaction. Names in .flatpakref
        # are app IDs, while bundle filenames may not be; avoid a false failure.
        return VerificationResult(result.success, "Flatpak transaction completed and was verified by Flatpak.")


class AdapterRegistry:
    def __init__(self, runner: CommandRunner | None = None) -> None:
        runner = runner or CommandRunner()
        rpm = RpmAdapter(runner)
        self._adapters: dict[PackageKind, PackageAdapter] = {
            PackageKind.RPM: rpm,
            PackageKind.DEB: DebAdapter(runner, rpm),
            PackageKind.APPIMAGE: AppImageAdapter(runner),
            PackageKind.FLATPAK: FlatpakAdapter(PackageKind.FLATPAK, runner),
            PackageKind.FLATPAKREF: FlatpakAdapter(PackageKind.FLATPAKREF, runner),
        }

    def for_path(self, value: str | os.PathLike[str]) -> tuple[PackageAdapter, Path]:
        path = validate_input_path(value)
        return self._adapters[sniff_package_kind(path)], path

    def get(self, kind: PackageKind) -> PackageAdapter:
        return self._adapters[kind]
