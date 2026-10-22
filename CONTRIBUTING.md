# Contributing to PackPort / 参与 PackPort

Thank you for helping make local package installation on Fedora safer and easier. 中文说明见下半部分。

## Build and run

PackPort currently targets Fedora 43. Install the development dependencies:

```sh
sudo dnf install meson ninja-build python3-gobject gtk4 libadwaita \
  gettext desktop-file-utils appstream libxml2 polkit flatpak alien dpkg \
  squashfs-tools rpm-build
```

Configure, compile, and run the test suite:

```sh
meson setup build
meson compile -C build
meson test -C build --print-errorlogs
```

Run the application directly from the source tree:

```sh
PYTHONPATH=src python3 -m packport.application
```

If `build/` was configured with a different Meson version or set of options, use `meson setup --wipe build` and configure it again.

## Reporting bugs

Before opening an issue, search the [existing issues](https://github.com/Tak1naa/PackPort/issues). Include:

- Fedora version, desktop session, CPU architecture, and PackPort version;
- package format and whether the install scope was current user or all users;
- exact steps, expected result, and actual result;
- the exported PackPort transaction log with private paths or package names redacted when needed.

Do not attach proprietary packages, credentials, or personal files. A failed DEB conversion is not automatically a PackPort bug; include the Alien and DNF error text so the compatibility boundary can be diagnosed.

For a vulnerability that could enable privilege escalation, command injection, path traversal, or unsafe package execution, do not publish exploit details in a public issue. Follow [`SECURITY.md`](SECURITY.md).

## Pull requests

1. Keep changes focused and preserve the fixed-command helper boundary.
2. Add or update tests for package sniffing, command construction, progress parsing, and security-sensitive paths.
3. Run the Meson test suite and the validation commands used by [CI](.github/workflows/ci.yml).
4. Update both `README.en.md` and `README.zh-CN.md` when user-visible behavior changes.
5. Explain what was tested and what remains unverified in the pull request.

By contributing, you agree that your contribution is licensed under GPL-3.0-or-later.

---

## 构建与运行

PackPort 当前以 Fedora 43 为主要目标。先安装依赖：

```sh
sudo dnf install meson ninja-build python3-gobject gtk4 libadwaita \
  gettext desktop-file-utils appstream libxml2 polkit flatpak alien dpkg \
  squashfs-tools rpm-build
```

配置、编译并运行测试：

```sh
meson setup build
meson compile -C build
meson test -C build --print-errorlogs
```

直接从源码运行：

```sh
PYTHONPATH=src python3 -m packport.application
```

如果 `build/` 来自不同 Meson 版本或不同选项，请执行 `meson setup --wipe build` 后重新配置。

## 报告问题

提交前先搜索[现有 Issues](https://github.com/Tak1naa/PackPort/issues)，并提供：

- Fedora 版本、桌面会话、CPU 架构和 PackPort 版本；
- 软件包格式，以及安装范围是当前用户还是所有用户；
- 可复现步骤、预期结果和实际结果；
- 必要时脱敏后的 PackPort 导出事务日志。

不要上传私有软件包、凭据或个人文件。DEB 转换失败不一定是 PackPort 缺陷，请一并提供 Alien 与 DNF 的错误信息，以便判断兼容性边界。

如果问题可能导致提权、命令注入、路径穿越或不安全执行软件包，请不要在公开 Issue 中发布利用细节，按 [`SECURITY.md`](SECURITY.md) 说明私下报告。

## 提交 Pull Request

1. 保持改动聚焦，不得破坏 helper 只接受固定子命令的安全边界。
2. 为格式识别、命令构造、进度解析和安全敏感路径补充测试。
3. 运行 Meson 测试和 [CI](.github/workflows/ci.yml) 中的验证命令。
4. 用户可见行为发生变化时，同时更新 `README.en.md` 与 `README.zh-CN.md`。
5. 在 PR 中明确已验证内容和仍未验证内容。

提交贡献即表示同意按 GPL-3.0-or-later 许可发布该贡献。
