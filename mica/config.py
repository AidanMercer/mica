import os
import tomllib
from pathlib import Path

CACHE_HOME = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "mica"
LOG_FILE = CACHE_HOME / "mica.log"

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "mica"
CONFIG_FILE = CONFIG_DIR / "config.toml"

_DEFAULTS = {
    "start": "",
    "show_hidden": False,
    "sort": "name",
    "terminal": "",
    "icons": True,
    "find_skip": [".git", "node_modules", ".cache", "__pycache__", ".venv"],
    "thumbnail_cache_mb": 200,
    "bookmarks": {},
}

# written to ~/.config/mica/config.toml on first run so there's something to edit
_TEMPLATE = """\
# mica config — everything here is optional; delete a line to use the default.
# edits apply live, except start / sort / show_hidden (those are read at launch).

# where mica opens when launched with no path (default: your home dir)
# start = "~/dev"

show_hidden = false
sort = "name"            # name | size | time

# nerd-font icons in the file list (needs a Nerd Font installed)
icons = true

# terminal for the `t` key (default: auto-detect kitty, foot, alacritty, …)
# terminal = "kitty"

# directories find (f) skips while walking the tree
find_skip = [".git", "node_modules", ".cache", "__pycache__", ".venv"]

# thumbnail cache cap, in MB
thumbnail_cache_mb = 200

# bookmarks — press g then the key to jump there.
# gg = top, gt = trash and gh = home are built in.
[bookmarks]
d = "~/dev"
D = "~/Downloads"
c = "~/.config"
"""


def ensure():
    """Drop a commented default config on first run so bookmarks etc. are
    discoverable. Best-effort — never blocks startup."""
    try:
        if not CONFIG_FILE.exists():
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(_TEMPLATE)
    except OSError:
        pass


def load():
    cfg = {k: (v.copy() if isinstance(v, (dict, list)) else v)
           for k, v in _DEFAULTS.items()}
    try:
        data = tomllib.loads(CONFIG_FILE.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return cfg
    for key in _DEFAULTS:
        if key in data:
            cfg[key] = data[key]
    return cfg


def save_bookmarks(bookmarks):
    """Rewrite just the [bookmarks] table in place, leaving the rest of the file
    (other settings, comments) untouched. stdlib has no toml writer, so this is a
    surgical block replacement rather than a full re-serialise."""
    def esc(v):
        return v.replace("\\", "\\\\").replace('"', '\\"')

    block = ["[bookmarks]"]
    block += [f'{k} = "{esc(str(bookmarks[k]))}"' for k in sorted(bookmarks)]

    try:
        lines = CONFIG_FILE.read_text().splitlines()
    except OSError:
        lines = []

    start = next((i for i, ln in enumerate(lines) if ln.strip() == "[bookmarks]"), None)
    if start is None:
        out = lines + ([""] if lines and lines[-1].strip() else []) + block
    else:
        end = next((j for j in range(start + 1, len(lines))
                    if lines[j].lstrip().startswith("[")), len(lines))
        out = lines[:start] + block + lines[end:]

    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text("\n".join(out).rstrip("\n") + "\n")
    except OSError:
        pass
