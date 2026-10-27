# Desktop file
desktop_conf = configuration_data()
desktop_conf.set('APP_ID', application_id)
desktop_file = configure_file(
  input: 'io.github.fastrizwaan.TeddyNotes.desktop.in',
  output: '@0@.desktop'.format(application_id),
  configuration: desktop_conf,
  install: true,
  install_dir: join_paths(get_option('datadir'), 'applications')
)

# AppStream Metainfo
metainfo_conf = configuration_data()
metainfo_conf.set('APP_ID', application_id)
metainfo_file = configure_file(
  input: 'io.github.fastrizwaan.TeddyNotes.metainfo.xml.in',
  output: '@0@.metainfo.xml'.format(application_id),
  configuration: metainfo_conf,
  install: true,
  install_dir: join_paths(get_option('datadir'), 'metainfo')
)

# GSettings Schema
install_data(
  'io.github.fastrizwaan.TeddyNotes.gschema.xml',
  install_dir: join_paths(get_option('datadir'), 'glib-2.0', 'schemas')
)

# Icons
install_data(
  'icons/hicolor/scalable/apps/io.github.fastrizwaan.TeddyNotes.svg',
  install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', 'scalable', 'apps')
)

install_data(
  'icons/hicolor/symbolic/apps/chain-link-symbolic.svg',
  'icons/hicolor/symbolic/apps/channel-secure-symbolic.svg',
  'icons/hicolor/symbolic/apps/checkbox-checked-symbolic.svg',
  'icons/hicolor/symbolic/apps/code-block-symbolic.svg',
  'icons/hicolor/symbolic/apps/code-symbolic.svg',
  'icons/hicolor/symbolic/apps/dialog-information-symbolic.svg',
  'icons/hicolor/symbolic/apps/document-edit-symbolic.svg',
  'icons/hicolor/symbolic/apps/document-save-as-symbolic.svg',
  'icons/hicolor/symbolic/apps/edit-clear-symbolic.svg',
  'icons/hicolor/symbolic/apps/edit-redo-symbolic.svg',
  'icons/hicolor/symbolic/apps/edit-select-all-symbolic.svg',
  'icons/hicolor/symbolic/apps/edit-symbolic.svg',
  'icons/hicolor/symbolic/apps/edit-undo-symbolic.svg',
  'icons/hicolor/symbolic/apps/eraser-symbolic.svg',
  'icons/hicolor/symbolic/apps/eraser3-symbolic.svg',
  'icons/hicolor/symbolic/apps/eye-open-negative-filled-symbolic.svg',
  'icons/hicolor/symbolic/apps/folder-download-symbolic.svg',
  'icons/hicolor/symbolic/apps/folder-new-symbolic.svg',
  'icons/hicolor/symbolic/apps/folder-open-symbolic.svg',
  'icons/hicolor/symbolic/apps/folder-symbolic.svg',
  'icons/hicolor/symbolic/apps/font-x-generic-symbolic.svg',
  'icons/hicolor/symbolic/apps/format-text-bold-symbolic.svg',
  'icons/hicolor/symbolic/apps/format-text-italic-symbolic.svg',
  'icons/hicolor/symbolic/apps/format-text-strikethrough-symbolic.svg',
  'icons/hicolor/symbolic/apps/format-text-underline-symbolic.svg',
  'icons/hicolor/symbolic/apps/go-previous-symbolic.svg',
  'icons/hicolor/symbolic/apps/heading-symbolic.svg',
  'icons/hicolor/symbolic/apps/insert-image-symbolic.svg',
  'icons/hicolor/symbolic/apps/insert-link-symbolic.svg',
  'icons/hicolor/symbolic/apps/insert-table-symbolic.svg',
  'icons/hicolor/symbolic/apps/io.github.fastrizwaan.TeddyNotes-symbolic.svg',
  'icons/hicolor/symbolic/apps/list-add-symbolic.svg',
  'icons/hicolor/symbolic/apps/list-remove-symbolic.svg',
  'icons/hicolor/symbolic/apps/marker-symbolic.svg',
  'icons/hicolor/symbolic/apps/non-starred-symbolic.svg',
  'icons/hicolor/symbolic/apps/object-select-symbolic.svg',
  'icons/hicolor/symbolic/apps/open-menu-symbolic.svg',
  'icons/hicolor/symbolic/apps/pan-down-symbolic.svg',
  'icons/hicolor/symbolic/apps/pan-end-symbolic.svg',
  'icons/hicolor/symbolic/apps/preferences-system-symbolic.svg',
  'icons/hicolor/symbolic/apps/printer-symbolic.svg',
  'icons/hicolor/symbolic/apps/quotation-symbolic.svg',
  'icons/hicolor/symbolic/apps/selection-mode-symbolic.svg',
  'icons/hicolor/symbolic/apps/sidebar-show-symbolic.svg',
  'icons/hicolor/symbolic/apps/starred-symbolic.svg',
  'icons/hicolor/symbolic/apps/system-search-symbolic.svg',
  'icons/hicolor/symbolic/apps/tag-symbolic.svg',
  'icons/hicolor/symbolic/apps/text-center-symbolic.svg',
  'icons/hicolor/symbolic/apps/text-editor-symbolic.svg',
  'icons/hicolor/symbolic/apps/user-home-symbolic.svg',
  'icons/hicolor/symbolic/apps/user-trash-symbolic.svg',
  'icons/hicolor/symbolic/apps/view-continuous-symbolic.svg',
  'icons/hicolor/symbolic/apps/view-grid-symbolic.svg',
  'icons/hicolor/symbolic/apps/view-list-bullet-symbolic.svg',
  'icons/hicolor/symbolic/apps/view-list-ordered-symbolic.svg',
  'icons/hicolor/symbolic/apps/view-list-symbolic.svg',
  'icons/hicolor/symbolic/apps/view-more-symbolic.svg',
  'icons/hicolor/symbolic/apps/x-office-document-symbolic.svg',
  install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', 'symbolic', 'apps')
)

install_data(
  'icons/hicolor/symbolic/apps/heading-symbolic.svg',
  install_dir: join_paths(get_option('datadir'), 'icons', 'hicolor', 'symbolic', 'actions')
)

# Assets (editor template, CSS)
install_subdir(
  '../assets',
  install_dir: pkgdatadir
)
