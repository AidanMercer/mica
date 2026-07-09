# todo

roughly in priority order. mica already handles nav, find, previews, the usual
file ops, trash + restore, zip/unzip, threaded ops, and config + bookmarks —
this is what's left.

## small wins
- [x] nerd-font icons per file type (uses Symbols Nerd Font, `icons` config toggle)
- [x] open-with menu — `o` lists apps for a file (default first), type to filter

## bigger
- [x] undo / redo — move, copy, trash, rename, create (ctrl-z / ctrl-shift-z)
- [x] content search — grep inside files with ripgrep (F)
- [x] system file picker — `mica --pick` + xdg-desktop-portal wrapper, so apps
      open mica to choose files (see `portal/`)
- [x] tabs — ctrl-t / ctrl-w / tab, per-tab cwd + cursor + marks (shared clipboard)
- [ ] per-theme `mica.qml` chrome slot, like frostify's, so themes can restyle more than the palette

## rough edges
- [x] live config reload — find_skip / terminal / cache / bookmarks apply on save
- [x] queue file ops instead of saying "busy" when one's already running
- [x] byte-level progress for a single big copy
- [ ] package it (PKGBUILD / AUR)
- [ ] cross-filesystem trash lands in the home trash (off-spec, still recoverable)
