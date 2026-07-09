# todo

roughly in priority order. mica already handles nav, find, previews, the usual
file ops, trash + restore, zip/unzip, threaded ops, and config + bookmarks —
this is what's left.

## small wins
- [x] nerd-font icons per file type (uses Symbols Nerd Font, `icons` config toggle)
- [ ] open-with menu — pick an app instead of always using xdg-open's default
- [ ] bulk rename — dump the marked names into `$EDITOR`, apply the diff on save

## bigger
- [x] undo / redo — move, copy, trash, rename, create (ctrl-z / ctrl-shift-z)
- [x] content search — grep inside files with ripgrep (F)
- [ ] tabs or split panes
- [ ] per-theme `mica.qml` chrome slot, like frostify's, so themes can restyle more than the palette

## rough edges
- [ ] live config reload — settings (sort, find_skip, cache cap) only apply at launch
- [ ] queue file ops instead of saying "busy" when one's already running
- [ ] byte-level progress for a single big copy (only item-level today)
- [ ] a test suite — everything's been checked by hand so far
- [ ] package it (PKGBUILD / AUR)
- [ ] cross-filesystem trash lands in the home trash (off-spec, still recoverable)
