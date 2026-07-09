# mica

A small GUI file manager that wears your [world80](https://github.com/AidanMercer/world80)
theme. Same idea as [frostify](https://github.com/AidanMercer/frostify) — a frosted-glass
Hyprland app that reads the active theme's palette and re-skins itself live when you
switch themes.

The layout is miller columns (parent · current · preview) with vim keys, in the shape of
[yazi](https://github.com/sxyazi/yazi), but it's a real window rather than a terminal UI —
so previews render actual images, video frames and pdf pages, and it opens as its own app.

Built with **PySide6 + QML**: Python walks the filesystem and handles file operations, QML
draws the panes. The glass look comes from a translucent window plus Hyprland's blur.

## Run

```bash
pip install -r requirements.txt      # or: pacman -S pyside6
./mica.sh                            # focuses an existing window, else launches
```

Video, PDF and audio-art previews shell out to `ffmpeg` and `poppler` (`pdftoppm`)
when they're installed; without them those files just show a summary card. Thumbnails
are cached under `~/.cache/mica/thumbnails`.

Bind it to a key and give it a launcher entry:

```ini
# ~/.config/hypr/hyprland.conf
bind = $mod, E, exec, ~/dev/mica/mica.sh
windowrule = opacity 1.0 override 1.0 override, class:mica
```

```bash
cp mica.desktop ~/.local/share/applications/
```

## Theming

The active theme is whatever `awww` is showing on the focused monitor; mica reads that
theme's `config.toml` (layered over `themes/default`), the same resolution the quickshell
loaders and frostify use, and derives its palette from the `accent*` / `hue_*` / `fg` / `bg`
tokens. It watches `~/.cache/awww` and the theme's `config.toml`, so switching or editing a
theme re-skins mica while it runs. `MICA_THEME=<name>` pins a theme for testing.

## Keys

| key | action | key | action |
| --- | --- | --- | --- |
| `j` `k` | move | `←`/`⌫` `l` | parent / open |
| `gg` `G` | top / bottom | `ctrl-d` `ctrl-u` | page |
| `/` `f` | filter dir / find recursive | `.` | toggle hidden |
| `space` | mark | `s` | cycle sort |
| `y` `x` `p` | yank / cut / paste | `d` `D` | trash / delete |
| `a` | create (`foo/` makes a dir) | `r` | rename |
| `z` `u` | zip / unzip into a folder | `t` | terminal here |
| `~` `gt` | home / go to trash | `q` / `esc` | quit |

Press `h` or `?` in-app for the cheat sheet. Mouse works too — click to select,
double-click to open. Files open with `xdg-open`.
