# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

project(
  'teddynotes',
  version: '1.6',
  meson_version: '>= 0.62.0',
  license: 'GPL-3.0-or-later'
)

i18n = import('i18n')
python = import('python')
gnome = import('gnome')

project_id = 'io.github.fastrizwaan.TeddyNotes'
project_name = 'Teddy Notes'

python_bin = python.find_installation('python3')
if not python_bin.found()
  error('No valid python3 binary found')
endif

python_dir = python_bin.get_install_dir()
pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), 'teddynotes')
localedir = join_paths(get_option('prefix'), get_option('localedir'))

application_id = project_id
if get_option('profile') == 'development'
  profile = 'Devel'
  application_id = '@0@.Devel'.format(application_id)
else
  profile = ''
endif

subdir('data')
subdir('teddynotes')
subdir('po')

gnome.post_install(
  gtk_update_icon_cache: true,
  glib_compile_schemas: true,
  update_desktop_database: true,
)
