from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class PackageKind(str, Enum):
    RPM = "rpm"
    DEB = "deb"
    APPIMAGE = "appimage"
    FLATPAK = "flatpak"
    FLATPAKREF = "flatpakref"


class InstallScope(str, Enum):
    USER = "user"
    SYSTEM = "system"


@dataclass(slots=True)
class PackageMetadata:
    path: Path
    kind: PackageKind
    name: str
    version: str = "Unknown"
    architecture: str = "Unknown"
    checksum: str = ""
    signature: str = "Unknown"
    description: str = ""
    size: int = 0
    warnings: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class InstallOptions:
    scope: InstallScope = InstallScope.USER
    include_maintainer_scripts: bool = False


@dataclass(slots=True)
class InstallPlan:
    metadata: PackageMetadata
    options: InstallOptions
    steps: list[str]
    requires_privilege: bool
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProgressEvent:
    stage: str
    fraction: float | None
    message: str
    cancelable: bool = True


@dataclass(slots=True)
class InstallResult:
    success: bool
    message: str
    installed_ref: str | None = None
    log_path: Path | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VerificationResult:
    success: bool
    message: str


class PackPortError(RuntimeError):
    """A user-presentable PackPort failure."""


class UnsupportedPackageError(PackPortError):
    pass


class CommandError(PackPortError):
    def __init__(self, message: str, returncode: int, output: str = "") -> None:
        super().__init__(message)
        self.returncode = returncode
        self.output = output


class CancelledError(PackPortError):
    pass

