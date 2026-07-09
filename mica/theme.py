import json
import os
import re
import subprocess
import tomllib
from pathlib import Path

from PySide6.QtCore import (Property, QFileSystemWatcher, QObject, QTimer,
                            QUrl, Signal)

THEMES_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "themes"
_AWWW_CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "awww"

# Frosted-dark defaults (tokyo-night-ish), used verbatim when no rice theme
# resolves. When one does, _build_theme() re-derives everything from the theme's
# config.toml tokens so mica follows the rest of the rice, light themes and all.
# Colors are #AARRGGBB — the window stays translucent so Hyprland's blur shows.
_BASE = {
    "bg":        "#66161a24",   # window glass
    "card":      "#ee161a24",   # near-opaque overlay (cheat sheet)
    "glassSoft": "#14ffffff",   # row hover
    "border":    "#30ffffff",
    "divider":   "#1affffff",

    "text":      "#ffc8ccd8",
    "subtext":   "#ff7e87b0",

    "sel":       "#ff7aa2f7",   # cursor pill on the active pane
    "selText":   "#ff11121a",   # ink on the pill
    "selDim":    "#3a7aa2f7",   # cursor pill when the pane is inactive
    "accent":    "#ff7aa2f7",
    "accent2":   "#ff7dcfff",
    "accentSoft":"#337aa2f7",

    # file-type ink, keyed by Fs kind
    "dir":       "#ff7dcfff",
    "link":      "#ff7aa2f7",
    "exec":      "#ff9ece6a",
    "image":     "#ffbb9af7",
    "video":     "#ffbb9af7",
    "audio":     "#ff7dcfff",
    "archive":   "#ffe0af68",
    "code":      "#ffc8ccd8",
    "doc":       "#ffc8ccd8",
    "file":      "#ffc8ccd8",

    "radius":   16,
    "radiusSm": 10,
    "pad":      12,
    "font":     "monospace",
}

# mirrors themes/default/config.toml — the fallback when even the default toml
# is missing, so keys always resolve.
_TOKEN_FALLBACK = {
    "accent":      "#7aa2f7",
    "accent2":     "#7dcfff",
    "accent3":     "#bb9af7",
    "accent_warn": "#e0af68",
    "accent_dim":  "#3b3f51",
    "hue_green":   "#9ece6a",
    "hue_blue":    "#7aa2f7",
    "fg":          "#c8ccd8",
    "bg":          "#11121a",
    "font_mono":   "monospace",
}


def _rgba(hex_color, alpha="ff"):
    """Theme tomls store opaque "#rrggbb"; QML wants "#aarrggbb". Prefix the
    alpha, pass 8-digit through, expand #rgb. None for anything unrecognised so
    the caller keeps its default."""
    h = hex_color.lstrip("#")
    if len(h) == 8:
        return "#" + h
    if len(h) == 6:
        return "#" + alpha + h
    if len(h) == 3:
        return "#" + alpha + "".join(c * 2 for c in h)
    return None


def _focused_monitor():
    """Name of the focused Hyprland monitor ("" if unknowable). Monitors can
    show different themes; mica should match the one being looked at."""
    try:
        out = subprocess.run(["hyprctl", "monitors", "-j"],
                             capture_output=True, text=True, timeout=2).stdout
        for m in json.loads(out):
            if m.get("focused"):
                return m.get("name", "")
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return ""


def _active_theme_dir():
    """Folder of the wallpaper awww shows on the focused monitor — the same
    resolution the quickshell loaders and frostify use. MICA_THEME (a name or a
    path) overrides it for headless testing. None if nothing resolves."""
    override = os.environ.get("MICA_THEME", "").strip()
    if override:
        p = Path(override).expanduser() if "/" in override else THEMES_DIR / override
        return p if p.is_dir() else None
    try:
        out = subprocess.run(["awww", "query"],
                             capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    mon = _focused_monitor()
    lines = out.splitlines()
    picked = next((l for l in lines if mon and f"{mon}:" in l), None)
    m = re.search(r"image:\s*(.+)", picked if picked is not None else out)
    if not m:
        return None
    d = Path(m.group(1).strip()).parent
    return d if d.is_dir() else None


def _read_tokens(theme_dir):
    """Theme config.toml layered over default/config.toml layered over the
    builtin fallback — flat keys, last write wins (same as the shell)."""
    tokens = dict(_TOKEN_FALLBACK)
    layers = [THEMES_DIR / "default" / "config.toml"]
    if theme_dir is not None:
        layers.append(theme_dir / "config.toml")
    for f in layers:
        try:
            tokens.update(tomllib.loads(f.read_text()))
        except (OSError, tomllib.TOMLDecodeError):
            pass
    return tokens


def _build_theme(tokens):
    """Re-derive mica's palette from the rice tokens. Chrome hairlines follow
    `fg` rather than white so light themes (shiro, guts) stay legible; file-type
    ink maps onto the palette hues."""
    theme = dict(_BASE)

    def col(key):
        v = tokens.get(key)
        return v if isinstance(v, str) and v.startswith("#") and _rgba(v) else None

    accent = col("accent")
    if accent:
        theme["accent"]     = _rgba(accent)
        theme["sel"]        = _rgba(accent)
        theme["selDim"]     = _rgba(accent, "3a")
        theme["accentSoft"] = _rgba(accent, "33")
        theme["link"]       = _rgba(accent)

    accent2 = col("accent2")
    if accent2:
        theme["accent2"] = _rgba(accent2)

    fg = col("fg") or col("text")
    if fg:
        theme["text"]    = _rgba(fg)
        theme["subtext"] = _rgba(fg, "aa")
        for k in ("code", "doc", "file"):
            theme[k] = _rgba(fg)

    txt = col("text") or col("fg")
    if txt:
        theme["border"]    = _rgba(txt, "30")
        theme["divider"]   = _rgba(txt, "1a")
        theme["glassSoft"] = _rgba(txt, "14")

    bg = col("bg")
    if bg:
        theme["bg"]      = _rgba(bg, "66")
        theme["card"]    = _rgba(bg, "ee")
        theme["selText"] = _rgba(bg)

    for token, keys in (("accent2", ("dir", "audio")),
                        ("accent3", ("image", "video")),
                        ("accent_warn", ("archive",)),
                        ("hue_green", ("exec",)),
                        ("hue_blue", ("code",))):
        c = col(token)
        if c:
            for k in keys:
                theme[k] = _rgba(c)

    font = tokens.get("font_mono")
    if isinstance(font, str) and font:
        theme["font"] = font

    return theme


class ThemeManager(QObject):
    """Follows the active rice theme (~/.config/themes/<x>) live.

    - palette: config.toml tokens -> the Theme dict all the QML binds to
    - chrome slot: the theme's optional mica.qml (same slot grammar as frostify
      and the shell's popup.qml — pal/host injection, backdrop/overlay Components)
    - watches ~/.cache/awww (touched on every wallpaper switch) plus the active
      theme's config.toml / mica.qml, so switching themes or editing them
      re-skins mica while it runs. themeChanged fires after each rebuild; main.py
      re-sets the Theme context property on it, which re-evaluates every Theme.*
      binding in the QML and reloads the chrome slot."""
    themeChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dir = None
        self._theme = dict(_BASE)
        self._pal = {}
        self._source = ""
        self._wants_pal = False
        self._wants_host = False
        self._nonce = 0
        self._snapshot = None

        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._poke)
        self._watcher.fileChanged.connect(self._poke)
        # a theme switch touches several files in a burst — coalesce them
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self._refresh)

        self._refresh(first=True)

    @Property(str, notify=themeChanged)
    def name(self):
        return self._dir.name if self._dir else ""

    @Property(str, notify=themeChanged)
    def themeDir(self):
        return str(self._dir) if self._dir else ""

    # -- chrome slot (the theme's optional mica.qml) --
    @Property(str, notify=themeChanged)
    def source(self):
        """file:// URL of the theme's mica.qml with a ?v= nonce (hot reload),
        or "" when the theme ships none."""
        return self._source

    @Property(bool, notify=themeChanged)
    def wantsPal(self):
        return self._wants_pal

    @Property(bool, notify=themeChanged)
    def wantsHost(self):
        return self._wants_host

    @Property("QVariantMap", notify=themeChanged)
    def pal(self):
        return self._pal

    def theme_dict(self):
        return self._theme

    def _poke(self, _path):
        self._debounce.start()

    def _refresh(self, first=False):
        d = _active_theme_dir()
        tokens = _read_tokens(d)

        qml = (d / "mica.qml") if d else None
        qml_stat = None
        qml_text = ""
        if qml is not None and qml.is_file():
            try:
                st = qml.stat()
                qml_stat = (st.st_mtime_ns, st.st_size)
                qml_text = qml.read_text()
            except OSError:
                qml_stat = None

        snapshot = (str(d) if d else "", tuple(sorted(
            (k, str(v)) for k, v in tokens.items())), qml_stat)
        self._rewatch(d)
        if snapshot == self._snapshot:
            return
        self._snapshot = snapshot

        self._dir = d
        self._theme = _build_theme(tokens)
        self._pal = {
            "neon":     tokens.get("accent", _TOKEN_FALLBACK["accent"]),
            "cyan":     tokens.get("accent2", _TOKEN_FALLBACK["accent2"]),
            "magenta":  tokens.get("accent3", _TOKEN_FALLBACK["accent3"]),
            "amber":    tokens.get("accent_warn", _TOKEN_FALLBACK["accent_warn"]),
            "dim":      tokens.get("accent_dim", _TOKEN_FALLBACK["accent_dim"]),
            "text":     tokens.get("fg") or tokens.get("text") or _TOKEN_FALLBACK["fg"],
            "glass":    tokens.get("glass") or tokens.get("bg") or _TOKEN_FALLBACK["bg"],
            "fontMono": tokens.get("font_mono", _TOKEN_FALLBACK["font_mono"]),
            "uiScale":  1.0,
            "themeDir": str(d) if d else "",
        }

        if qml_stat is not None:
            # same handshake as frostify / the shell's loaders: grep the file
            # for the literal property declarations to decide what to inject
            self._wants_pal = "property var pal" in qml_text
            self._wants_host = "property var host" in qml_text
            self._nonce += 1
            self._source = QUrl.fromLocalFile(str(qml)).toString() + f"?v={self._nonce}"
        else:
            self._wants_pal = self._wants_host = False
            self._source = ""

        print(f"[theme] {self._dir.name if self._dir else '(defaults)'}"
              f"  chrome={'mica.qml' if self._source else 'none'}", flush=True)
        if not first:
            self.themeChanged.emit()

    def _rewatch(self, d):
        want = [_AWWW_CACHE] + [p for p in _AWWW_CACHE.glob("*") if p.is_dir()]
        want += [THEMES_DIR / "default" / "config.toml"]
        if d is not None:
            want += [d, d / "config.toml", d / "mica.qml"]
        have = set(self._watcher.directories()) | set(self._watcher.files())
        missing = [str(p) for p in want if p.exists() and str(p) not in have]
        if missing:
            self._watcher.addPaths(missing)
