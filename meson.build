project(
  'packport',
  version: '0.1.0',
  meson_version: '>= 1.3.0',
)

gnome = import('gnome')
i18n = import('i18n')
# PackPort targets Fedora and its RPM dependency generator must see the stable
# system interpreter path, not a developer's pyenv/virtualenv shim.
python = import('python').find_installation('/usr/bin/python3')

conf = configuration_data()
conf.set('PYTHON', python.full_path())
conf.set_quoted('VERSION', meson.project_version())
conf.set_quoted('LOCALEDIR', get_option('prefix') / get_option('localedir'))

configure_file(
  input: 'src/packport.in',
  output: 'packport',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)

configure_file(
  input: 'src/packport-helper.in',
  output: 'packport-helper',
  configuration: conf,
  install: true,
  install_dir: get_option('libexecdir'),
  install_mode: 'rwxr-xr-x',
)

python.install_sources(
  'src/packport/__init__.py',
  'src/packport/application.py',
  'src/packport/adapters.py',
  'src/packport/models.py',
  'src/packport/runner.py',
  'src/packport/security.py',
  'src/packport/transactions.py',
  subdir: 'packport',
)

install_data(
  'data/io.github.packport.PackPort.desktop',
  install_dir: get_option('datadir') / 'applications',
)
install_data(
  'data/io.github.packport.PackPort.metainfo.xml',
  install_dir: get_option('datadir') / 'metainfo',
)
install_data(
  'data/io.github.packport.PackPort.policy',
  install_dir: get_option('datadir') / 'polkit-1/actions',
)
install_data(
  'data/io.github.packport.PackPort.xml',
  install_dir: get_option('datadir') / 'mime/packages',
)
install_data(
  'data/icons/hicolor/scalable/apps/io.github.packport.PackPort.svg',
  install_dir: get_option('datadir') / 'icons/hicolor/scalable/apps',
)

subdir('po')

test(
  'unit',
  python,
  args: ['-m', 'unittest', 'discover', '-s', meson.project_source_root() / 'tests', '-v'],
  env: ['PYTHONPATH=' + meson.project_source_root() / 'src'],
)
