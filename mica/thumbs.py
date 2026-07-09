import hashlib
import shutil
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

from . import config


class Thumbnailer(QObject):
    """Renders a cached PNG for files QML can't draw directly — video frames, pdf
    pages, embedded audio art — and emits ready(src, thumb) when one lands.
    Generation runs in a QProcess so hovering never blocks the UI. Thumbs are
    keyed by path + mtime + size, so an edited file re-renders."""
    ready = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dir = config.CACHE_HOME / "thumbnails"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._running = {}
        self._ffmpeg = shutil.which("ffmpegthumbnailer") or shutil.which("ffmpeg")
        self._pdftoppm = shutil.which("pdftoppm")

    def get(self, path: Path, kind: str) -> str:
        """Cached thumbnail path, or "" while one is generated in the background."""
        try:
            st = path.stat()
        except OSError:
            return ""
        key = hashlib.sha1(f"{path}:{st.st_mtime_ns}:{st.st_size}".encode()).hexdigest()
        out = self._dir / f"{key}.png"
        if out.exists():
            return str(out)
        self._start(key, path, kind, out)
        return ""

    def _start(self, key, path, kind, out):
        if key in self._running:
            return
        cmd = self._command(path, kind, out)
        if cmd is None:
            return
        proc = QProcess(self)
        proc.finished.connect(lambda *_: self._finish(key, path, out))
        proc.errorOccurred.connect(lambda *_: self._running.pop(key, None))
        self._running[key] = proc
        proc.start(cmd[0], cmd[1:])

    def _finish(self, key, path, out):
        self._running.pop(key, None)
        if out.exists() and out.stat().st_size > 0:
            self.ready.emit(str(path), str(out))

    def _command(self, path, kind, out):
        src, dst = str(path), str(out)
        if kind in ("video", "audio") and self._ffmpeg:
            if Path(self._ffmpeg).name == "ffmpegthumbnailer":
                return [self._ffmpeg, "-i", src, "-o", dst, "-s", "640", "-q", "8"]
            if kind == "video":
                return [self._ffmpeg, "-y", "-loglevel", "error", "-ss", "1",
                        "-i", src, "-frames:v", "1", "-vf", "scale=640:-1", dst]
            # audio: grab the embedded cover art, if the file has any
            return [self._ffmpeg, "-y", "-loglevel", "error", "-i", src,
                    "-an", "-frames:v", "1", dst]
        if kind == "pdf" and self._pdftoppm:
            # -singlefile makes pdftoppm append .png to the prefix we give it
            return [self._pdftoppm, "-png", "-f", "1", "-l", "1",
                    "-scale-to", "900", "-singlefile", src, dst[:-4]]
        return None
