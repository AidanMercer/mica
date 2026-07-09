import sys
import time
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QTimer, QUrl, qInstallMessageHandler
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QSurfaceFormat
from PySide6.QtQml import QQmlApplicationEngine

from . import config
from .fs import Fs
from .picker import Picker
from .theme import ThemeManager

_LOG_CAP = 1024 * 1024


class _Tee:
    """Fan writes to several streams so everything lands in the log even when the
    launcher sends stdout to /dev/null."""
    def __init__(self, *streams):
        self._streams = [s for s in streams if s is not None]

    def write(self, s):
        for st in self._streams:
            try:
                st.write(s)
                st.flush()
            except Exception:
                pass

    def flush(self):
        for st in self._streams:
            try:
                st.flush()
            except Exception:
                pass


def _start_logging():
    try:
        config.CACHE_HOME.mkdir(parents=True, exist_ok=True)
        mode = "w" if (config.LOG_FILE.exists()
                       and config.LOG_FILE.stat().st_size > _LOG_CAP) else "a"
        logf = open(config.LOG_FILE, mode, buffering=1)
    except Exception:
        return
    sys.stdout = _Tee(sys.__stdout__, logf)
    sys.stderr = _Tee(sys.__stderr__, logf)
    print(f"\n==== mica session {time.strftime('%Y-%m-%d %H:%M:%S')} ====", flush=True)


def _qt_message_handler(mode, ctx, msg):
    loc = f" ({ctx.file}:{ctx.line})" if ctx.file else ""
    print(f"[qml] {msg}{loc}", file=sys.stderr, flush=True)


def _icon_font(cfg):
    """A nerd font for file-type glyphs, or "" to fall back to no icons. Uses a
    dedicated icon font rather than the theme font, so glyphs render even when
    the theme's mono font isn't nerd-patched."""
    if not cfg.get("icons", True):
        return ""
    families = QFontDatabase.families()
    for pref in ("Symbols Nerd Font Mono", "Symbols Nerd Font"):
        if pref in families:
            return pref
    return next((f for f in families if "Nerd Font" in f), "")


def _start_dir(argv, cfg):
    for arg in argv[1:]:
        if not arg.startswith("-"):
            p = Path(arg).expanduser()
            if p.is_dir():
                return p.resolve()
    start = cfg.get("start", "")
    if start:
        p = Path(start).expanduser()
        if p.is_dir():
            return p.resolve()
    return Path.home()


def _parse_pick(argv):
    """--pick turns mica into a portal file chooser. Flags mirror the
    xdg-desktop-portal FileChooser request; returns None for normal launch."""
    if "--pick" not in argv:
        return None
    opts = {"multiple": False, "directory": False, "save": False, "out": "", "name": ""}
    it = iter(argv[1:])
    for a in it:
        if a == "--multiple":
            opts["multiple"] = True
        elif a == "--directory":
            opts["directory"] = True
        elif a == "--save":
            opts["save"] = True
        elif a == "--out":
            opts["out"] = next(it, "")
        elif a == "--name":
            opts["name"] = next(it, "")
    return opts


def main():
    _start_logging()

    # let the window be translucent so Hyprland blurs behind it
    fmt = QSurfaceFormat()
    fmt.setAlphaBufferSize(8)
    QSurfaceFormat.setDefaultFormat(fmt)
    qInstallMessageHandler(_qt_message_handler)

    pick = _parse_pick(sys.argv)

    app = QGuiApplication(sys.argv)
    app.setApplicationName("mica")
    # app_id is the Wayland class Hyprland matches. In pick mode use a distinct
    # class so a window rule can float the picker without touching normal mica.
    app.setDesktopFileName("mica-picker" if pick else "mica")

    config.ensure()
    cfg = config.load()

    theme = ThemeManager(app)
    fs = Fs(_start_dir(sys.argv, cfg), cfg)

    def apply_font():
        app.setFont(QFont(theme.theme_dict()["font"]))
    apply_font()

    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("Theme", theme.theme_dict())
    ctx.setContextProperty("Rice", theme)
    ctx.setContextProperty("fs", fs)
    ctx.setContextProperty("iconFont", _icon_font(cfg))
    # parent to app + keep the ref so PySide doesn't gc it out from under QML
    picker = Picker(app, pick, parent=app) if pick else None
    ctx.setContextProperty("picker", picker)

    def retheme():
        ctx.setContextProperty("Theme", theme.theme_dict())
        apply_font()
    theme.themeChanged.connect(retheme)

    # live config reload — watch the file (and its dir, since editors replace it)
    watcher = QFileSystemWatcher(app)
    debounce = QTimer(app)
    debounce.setSingleShot(True)
    debounce.setInterval(250)

    def reload_config():
        fresh = config.load()
        fs.applyConfig(fresh)
        ctx.setContextProperty("iconFont", _icon_font(fresh))
        if config.CONFIG_FILE.exists() and str(config.CONFIG_FILE) not in watcher.files():
            watcher.addPath(str(config.CONFIG_FILE))

    debounce.timeout.connect(reload_config)
    watcher.fileChanged.connect(lambda _p: debounce.start())
    watcher.directoryChanged.connect(lambda _p: debounce.start())
    watcher.addPath(str(config.CONFIG_DIR))
    if config.CONFIG_FILE.exists():
        watcher.addPath(str(config.CONFIG_FILE))

    engine.load(QUrl.fromLocalFile(str(Path(__file__).parent / "qml" / "Main.qml")))
    if not engine.rootObjects():
        sys.exit(1)
    sys.exit(app.exec())
