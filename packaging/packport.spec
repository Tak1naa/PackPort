Name:           packport
Version:        0.1.0
Release:        1%{?dist}
Summary:        Safe drag-and-drop package installer for Fedora
License:        GPL-3.0-or-later
URL:            https://github.com/Tak1naa/PackPort
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  meson
BuildRequires:  gettext
BuildRequires:  desktop-file-utils
BuildRequires:  appstream
BuildRequires:  python3-devel
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Requires:       polkit
Requires:       dnf5
Requires:       rpm
Requires:       flatpak
Requires:       alien
Requires:       dpkg
Requires:       squashfs-tools
Requires:       rpm-build

%description
PackPort inspects and installs RPM, DEB, AppImage, Flatpak bundle, and Flatpak
reference files through a focused Fedora desktop interface.

%prep
%autosetup

%build
%meson
%meson_build

%install
%meson_install
%find_lang packport
desktop-file-validate %{buildroot}%{_datadir}/applications/io.github.packport.PackPort.desktop
appstreamcli validate --no-net %{buildroot}%{_metainfodir}/io.github.packport.PackPort.metainfo.xml

%files -f packport.lang
%license LICENSE
%doc README.md README.zh-CN.md README.en.md CONTRIBUTING.md ROADMAP.md SECURITY.md NOTICE
%{_bindir}/packport
%{_libexecdir}/packport-helper
%{python3_sitelib}/packport/
%{_datadir}/applications/io.github.packport.PackPort.desktop
%{_metainfodir}/io.github.packport.PackPort.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/io.github.packport.PackPort.svg
%{_datadir}/mime/packages/io.github.packport.PackPort.xml
%{_datadir}/polkit-1/actions/io.github.packport.PackPort.policy

%changelog
* Thu Aug 27 2026 PackPort contributors - 0.1.0-1
- Initial Fedora 43 release
