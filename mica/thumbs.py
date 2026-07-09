import hashlib
import os
import shutil
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

from . import config

_MAX_JOBS = 3                       # concurrent render processes
_MAX_QUEUE = 32                     # pending renders kept while scrolling fast


class Thumbnailer(QObject):
    """Renders a cached PNG for files QML can't draw directly — video frames, pdf
    pages, embedded audio art — and emits ready(src, thumb) when one lands.
    Generation runs in a QProcess so hovering never blocks the UI. Thumbs are
    keyed by path + mtime + size, so an edited file re-renders."""
    ready = Signal(str, str)

    def __init__(self, cache_mb=200, parent=None):
        super().__init__(parent)
        self._limit = max(1, int(cache_mb)) * 1024 * 1024
        self._dir = config.CACHE_HOME / "thumbnails"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._running = {}          # key -> QProcess
        self._queue = []            # (key, path, out, cmd), consumed newest-first
        self._queued = set()
        self._ffmpeg = shutil.which("ffmpegthumbnailer") or shutil.which("ffmpeg")
        self._pdftoppm = shutil.which("pdftoppm")
        self._bytes = self._evict()

    def get(self, path: Path, kind: str) -> str:
        """Cached thumbnail path, or "" while one is generated in the background."""
        try:
            st = path.stat()
        except OSError:
            return ""
        key = hashlib.sha1(f"{path}:{st.st_mtime_ns}:{st.st_size}".encode()).hexdigest()
        out = self._dir / f"{key}.png"
        if out.exists():
            self._touch(out)        # mark recently used for the LRU sweep
            return str(out)
        self._enqueue(key, path, kind, out)
        return ""

    # --- scheduling ------------------------------------------------------

    def _enqueue(self, key, path, kind, out):
        if key in self._running or key in self._queued:
            return
        cmd = self._command(path, kind, out)
        if cmd is None:
            return
        if len(self._running) < _MAX_JOBS:
            self._spawn(key, path, out, cmd)
            return
        if len(self._queue) >= _MAX_QUEUE:
            dropped = self._queue.pop(0)     # shed the stalest pending render
            self._queued.discard(dropped[0])
        self._queue.append((key, path, out, cmd))
        self._queued.add(key)

    def _spawn(self, key, path, out, cmd):
        proc = QProcess(self)
        proc.finished.connect(lambda *_: self._done(key, path, out))
        proc.errorOccurred.connect(lambda *_: self._done(key, path, out))
        self._running[key] = proc
        proc.start(cmd[0], cmd[1:])

    def _done(self, key, path, out):
        if key not in self._running:
            return                  # finished + errorOccurred can both fire
        self._running.pop(key, None)
        if out.exists() and out.stat().st_size > 0:
            self._bytes += out.stat().st_size
            if self._bytes > self._limit:
                self._bytes = self._evict()
            self.ready.emit(str(path), str(out))
        self._pump()

    def _pump(self):
        while self._queue and len(self._running) < _MAX_JOBS:
            key, path, out, cmd = self._queue.pop()   # newest hover first
            self._queued.discard(key)
            self._spawn(key, path, out, cmd)

    # --- cache -----------------------------------------------------------

    def _touch(self, path):
        try:
            os.utime(path)
        except OSError:
            pass

    def _evict(self):
        try:
            files = [(p, p.stat()) for p in self._dir.glob("*.png")]
        except OSError:
            return 0
        total = sum(st.st_size for _, st in files)
        if total <= self._limit:
            return total
        target = int(self._limit * 0.8)   # low-water mark so we don't sweep every run
        for p, st in sorted(files, key=lambda f: f[1].st_mtime):
            if total <= target:
                break
            try:
                p.unlink()
                total -= st.st_size
            except OSError:
                pass
        return total

    # --- commands --------------------------------------------------------

    def _command(self, path, kind, out):
        src, dst = str(path), str(out)
        if kind in ("video", "audio") and self._ffmpeg:
            if Path(self._ffmpeg).name == "ffmpegthumbnailer":
                return [self._ffmpeg, "-i", src, "-o", dst, "-s", "640", "-q", "8"]
            if kind == "video":
                return [self._ffmpeg, "-y", "-loglevel", "error", "-ss", "1",
                        "-i", src, "-frames:v", "1", "-vf", "scale=640:-1", dst]
            # audio: pull the embedded cover art, if the file has any
            return [self._ffmpeg, "-y", "-loglevel", "error", "-i", src,
                    "-an", "-frames:v", "1", dst]
        if kind == "pdf" and self._pdftoppm:
            # -singlefile makes pdftoppm append .png to the prefix we give it
            return [self._pdftoppm, "-png", "-f", "1", "-l", "1",
                    "-scale-to", "900", "-singlefile", src, dst[:-4]]
        return None
