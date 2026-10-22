# PackPort roadmap

PackPort follows a safety-first roadmap. The public GitHub issues linked below are the source of truth for scope and progress; target versions may change as Fedora and package tooling evolve.

## v0.2.0 — compatibility and diagnostics

- [#1 — Expand the Fedora 43 compatibility matrix](https://github.com/Tak1naa/PackPort/issues/1) across representative RPM, DEB, AppImage, Flatpak bundle, and Flatpak reference packages.
- [#2 — Improve actionable backend error handling](https://github.com/Tak1naa/PackPort/issues/2) for DNF5, Alien, Flatpak, Polkit cancellation, and network failures.
- [#4 — Add a reproducible Fedora 43 VM release checklist](https://github.com/Tak1naa/PackPort/issues/4) with end-to-end checks and residue verification.

## v0.3.0 — installation hardening

- [#3 — Audit and harden installation security boundaries](https://github.com/Tak1naa/PackPort/issues/3), including the privileged helper, path validation, symlink/race handling, temporary files, and cancellation boundaries.
- Improve signature and publisher information without offering bypass switches.
- Continue accessibility and localization review for confirmation, progress, and error states.

## Out of scope for the current roadmap

PackPort is not becoming an app store or a universal package converter. Online search, update management, Snap, generic archives, and dependency-check bypasses remain out of scope unless the security and maintenance model changes substantially.

See all work items in the [GitHub issue tracker](https://github.com/Tak1naa/PackPort/issues).
