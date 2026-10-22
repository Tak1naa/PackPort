# Security policy

PackPort installs untrusted package formats and includes a narrowly scoped privileged helper. Security reports are therefore handled separately from ordinary bug reports.

Please report suspected privilege escalation, command injection, path traversal, unsafe package execution, or helper-policy bypass privately through [GitHub private vulnerability reporting](https://github.com/Tak1naa/PackPort/security/advisories/new). Include the affected version, reproduction steps, and impact. Do not attach secrets or personal packages.

General hardening ideas that do not disclose an exploitable vulnerability may be discussed in the public issue tracker.

The currently supported release line is `0.1.x` on Fedora 43 x86_64. Maintainers will acknowledge a complete security report as soon as practical and coordinate disclosure after a fix is available.
