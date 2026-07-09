import sys
import time
from pathlib import Path

from PySide6.QtCore import QUrl, qInstallMessageHandler
from PySide6.QtGui import QFont, QGuiApplication, QSurfaceFormat
from PySide6.QtQml import QQmlApplicationEngine

from . import config
from .fs import Fs
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


def main():
    _start_logging()

    # let the window be translucent so Hyprland blurs behind it
    fmt = QSurfaceFormat()
    fmt.setAlphaBufferSize(8)
    QSurfaceFormat.setDefaultFormat(fmt)
    qInstallMessageHandler(_qt_message_handler)

    app = QGuiApplication(sys.argv)
    app.setApplicationName("mica")
    app.setDesktopFileName("mica")  # becomes the Wayland app_id Hyprland matches

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

    def retheme():
        ctx.setContextProperty("Theme", theme.theme_dict())
        apply_font()
    theme.themeChanged.connect(retheme)

    engine.load(QUrl.fromLocalFile(str(Path(__file__).parent / "qml" / "Main.qml")))
    if not engine.rootObjects():
        sys.exit(1)
    sys.exit(app.exec())
