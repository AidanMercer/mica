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

Beyond the palette, a theme can ship a **`mica.qml` chrome slot** (same grammar as
frostify's `frostify.qml`): an invisible `Item` that mica loads with the theme's `pal`
snapshot and the mica `host` window injected. It can restyle the window frame
(`cardBg` / `cardBorder` / `cardBorderWidth` / `cardRadius`), mount `backdrop` / `overlay`
`Component`s behind and above the miller columns (shaders, particles, Canvas — auto-masked
to the window's rounded corners), and set a status-bar `wordmark`. Continuous motion gates
on window focus (`host.active`); one-shot flourishes fire on a directory change
(`host.navId`). mica.qml hot-reloads with the rest of the theme. See the reference file in
`themes/default/mica.qml` and the full contract in `themes/AI-INSTRUCTION.md`.

## Config

mica writes a commented `~/.config/mica/config.toml` on first run (there's a
`config.example.toml` in the repo too). It's all optional — start dir, default
sort, whether to show hidden files, nerd-font icons (needs a Nerd Font — mica
uses the icon-only *Symbols Nerd Font* if present), the terminal for `t`, the
dirs `f` skips, the thumbnail cache cap, and bookmarks:

```toml
[bookmarks]
d = "~/dev"
D = "~/Downloads"
c = "~/.config"
```

Edits to the config apply live (mica watches the file) — except `start`, `sort`
and `show_hidden`, which are read at launch.

Press `g` then the key to jump (`gg` top, `gt` trash, `gh` home are built in). A
hint of the available jumps shows in the status bar the moment you press `g`.

You can also manage bookmarks without editing the file: **`ga`** on a folder asks
which key to map it to, **`gr`** removes one (with a confirm). Both write back to
the config. `g t h a r` are reserved as bookmark keys.

## As your system file picker

mica can be the picker every app opens when it asks you to choose a file — browser
uploads, "Open File…" in an editor, attaching in a chat app — instead of the GTK
dialog. It hooks in through `xdg-desktop-portal`, so it works across portal-aware
apps. See [`portal/`](portal/) — install the backend, run `portal/setup.sh`, done.
Under the hood it's `mica --pick`, a normal mica window that returns the selected
path rather than opening it.

## Keys

| key | action | key | action |
| --- | --- | --- | --- |
| `j` `k` | move | `←`/`⌫` `l` | parent / open |
| `gg` `G` | top / bottom | `ctrl-d` `ctrl-u` | page |
| `/` `f` `F` | filter · find name · grep files | `.` | toggle hidden |
| `space` | mark | `s` | cycle sort |
| `y` `x` `p` | yank / cut / paste | `d` `D` | trash / delete |
| `a` | create (`foo/` makes a dir) | `r` | rename |
| `z` `u` | zip / unzip into a folder | `t` | terminal here |
| `ctrl-z` | undo | `ctrl-⇧-z` `ctrl-y` | redo |
| `~` `gt` | home / go to trash | `q` / `esc` | quit |

Press `h` or `?` in-app for the cheat sheet. `gt` jumps to the trash, where `p`
puts an item back where it came from. Mouse works too — click to select,
double-click to open. Files open with `xdg-open`.

Paste never overwrites: pasting `foo.txt` where one already exists lands as
`foo_1.txt` (and so on). Undo with `ctrl-z` if that wasn't what you wanted.
