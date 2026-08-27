# PackPort

PackPort 是一个面向 Fedora 的原生桌面软件包安装器。将软件包拖入窗口，检查安装信息，选择安装范围，然后查看安装进度，无需打开终端。

## 支持格式

- `.rpm`：使用 DNF5 安装，并检查 RPM 元数据、架构和签名。
- `.deb`：使用 Alien 在普通用户环境中转换为临时 RPM，再交给 DNF5 安装。Debian 维护脚本默认关闭，启用前需要二次确认。
- `.AppImage`：复制到 PackPort 管理目录并创建桌面启动项，支持当前用户或全系统安装。
- `.flatpak`：使用 Flatpak bundle 安装。
- `.flatpakref`：使用 Flatpak reference 安装，可能需要联网添加远程仓库并下载运行时。

压缩包和未知格式不会被强行安装。DEB 转换也不保证软件一定兼容 Fedora；PackPort 不会使用 `--nodeps`、`--skip-broken` 或 `--allowerasing` 绕过依赖检查。

## 安装

Fedora 43 x86_64 RPM：

```sh
sudo dnf install ./dist/packport-0.1.0-1.fc43.noarch.rpm
```

安装后可从应用菜单启动，或运行：

```sh
packport
```

## 功能

- 全窗口拖放和多文件顺序队列。
- 安装前显示包名、版本、架构、签名、SHA-256、来源和风险提示。
- AppImage 与 Flatpak 支持“当前用户 / 所有用户”范围选择。
- DNF、Alien、Flatpak 输出会实时显示为阶段或百分比进度。
- 事务日志保存到 `~/.local/state/packport/transactions/`，支持导出。
- 简体中文和英文界面，支持 MIME/Open With 文件关联。

## 开发环境

在 Fedora 43 上安装依赖：

```sh
sudo dnf install meson ninja-build python3-gobject gtk4 libadwaita \
  gettext desktop-file-utils appstream polkit flatpak alien dpkg \
  squashfs-tools rpm-build
```

构建、测试和安装到临时目录：

```sh
meson setup build
meson compile -C build
meson test -C build --print-errorlogs
meson install -C build --destdir "$PWD/stage"
```

直接从源码运行：

```sh
PYTHONPATH=src python3 -m packport.application
```

## 安全模型

图形界面进程始终以普通用户运行。RPM 安装和全系统 AppImage 集成通过受限的 Polkit helper 执行；helper 只接受固定子命令，不接受任意 shell 命令。

输入路径会解析并验证为普通文件，所有外部命令都使用参数数组。检查包元数据时不会执行输入文件，AppImage 集成使用临时文件和原子重命名。

DNF 进入事务提交阶段后不可取消，以避免破坏 RPM 数据库。安装失败会保留诊断日志，但不会伪造“已回滚”状态。

## 项目与许可

PackPort 使用 GPL-3.0-or-later。AppImage 集成的设计参考了 [Gear Lever](https://github.com/mijorus/gearlever)，归属和许可信息见 [`NOTICE`](NOTICE)。

PackPort 当前不包含软件商店、在线搜索、更新管理、Snap 或通用归档包安装功能。

