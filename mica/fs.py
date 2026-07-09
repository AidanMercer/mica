import os
import shutil
import stat
import subprocess
import time
import zipfile
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot

_PREVIEW_BYTES = 64 * 1024

_IMAGE = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "svg", "ico", "tiff", "avif", "heic"}
_VIDEO = {"mp4", "mkv", "webm", "mov", "avi", "flv", "wmv", "m4v"}
_AUDIO = {"mp3", "flac", "wav", "ogg", "m4a", "opus", "aac"}
_ARCHIVE = {"zip", "tar", "gz", "tgz", "xz", "bz2", "zst", "7z", "rar", "lz4"}
_CODE = {"rs", "go", "py", "js", "ts", "jsx", "tsx", "c", "h", "cpp", "hpp", "java",
         "rb", "lua", "sh", "fish", "vim", "qml", "toml", "yaml", "yml", "json",
         "css", "html"}
_DOC = {"pdf", "txt", "md", "doc", "docx", "odt", "epub"}

# longest-first so ".tar.gz" wins over ".tar"; only formats shutil can unpack
_ARCHIVE_SUFFIXES = (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".zip", ".tar")
_TERMINALS = ("kitty", "alacritty", "foot", "wezterm", "ghostty", "konsole",
              "gnome-terminal", "xterm")


def _kind(path: Path, is_dir: bool, is_link: bool, is_exec: bool) -> str:
    if is_dir:
        return "dir"
    if is_link:
        return "link"
    ext = path.suffix.lower().lstrip(".")
    if ext in _IMAGE:
        return "image"
    if ext in _VIDEO:
        return "video"
    if ext in _AUDIO:
        return "audio"
    if ext in _ARCHIVE:
        return "archive"
    if ext in _CODE:
        return "code"
    if ext in _DOC:
        return "doc"
    return "exec" if is_exec else "file"


def _human_size(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    size = float(n)
    for unit in "KMGTP":
        size /= 1024
        if size < 1024:
            return f"{size:.0f}{unit}" if size >= 100 else f"{size:.1f}{unit}"
    return f"{size:.0f}P"


def _rel_time(secs: float) -> str:
    delta = max(0, int(time.time() - secs))
    for limit, div, suffix in ((60, 1, "s"), (3600, 60, "m"), (86400, 3600, "h"),
                               (86400 * 30, 86400, "d"), (86400 * 365, 86400 * 30, "mo")):
        if delta < limit:
            return f"{delta // div}{suffix}"
    return f"{delta // (86400 * 365)}y"


def _perms(mode: int, is_dir: bool, is_link: bool) -> str:
    ty = "l" if is_link else "d" if is_dir else "-"
    flags = "rwxrwxrwx"
    bits = [stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR,
            stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP,
            stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH]
    return ty + "".join(f if mode & b else "-" for f, b in zip(flags, bits))


def _entry(path: Path, marked: set) -> dict:
    try:
        lstat = path.lstat()
    except OSError:
        lstat = None
    is_link = bool(lstat and stat.S_ISLNK(lstat.st_mode))
    try:
        st = path.stat()  # follows symlinks
    except OSError:
        st = None
    is_dir = bool(st and stat.S_ISDIR(st.st_mode))
    size = st.st_size if st else 0
    mode = st.st_mode if st else 0
    is_exec = not is_dir and bool(mode & 0o111)
    mtime = lstat.st_mtime if lstat else 0
    return {
        "name": path.name,
        "path": str(path),
        "isDir": is_dir,
        "isLink": is_link,
        "size": size,
        "mtime": mtime,
        "sizeText": "" if is_dir else _human_size(size),
        "mtimeText": _rel_time(mtime) if mtime else "-",
        "perms": _perms(mode, is_dir, is_link),
        "kind": _kind(path, is_dir, is_link, is_exec),
        "marked": str(path) in marked,
    }


def _archive_stem(name: str):
    low = name.lower()
    for suf in _ARCHIVE_SUFFIXES:
        if low.endswith(suf):
            return name[: -len(suf)]
    return None


def _zip_tree(zf, base: Path, arc_prefix: Path):
    for root, dirs, files in os.walk(base):
        root_p = Path(root)
        rel = root_p.relative_to(base)
        for f in files:
            zf.write(root_p / f, str(arc_prefix / rel / f))
        # an empty dir has no files to imply it — store it explicitly or it's lost
        if not files and not dirs:
            entry = str(arc_prefix / rel)
            if entry not in (".", ""):
                zf.writestr(entry + "/", "")


def _dedupe(dst: Path) -> Path:
    if not dst.exists():
        return dst
    stem, suffix = dst.stem, dst.suffix
    i = 1
    while True:
        cand = dst.with_name(f"{stem}_{i}{suffix}")
        if not cand.exists():
            return cand
        i += 1


class Fs(QObject):
    dirChanged = Signal()      # cwd / entries / parent changed
    flagsChanged = Signal()    # hidden or sort
    clipChanged = Signal()
    notify = Signal(str, bool)  # message, isError

    def __init__(self, start: Path, parent=None):
        super().__init__(parent)
        self._cwd = start
        self._show_hidden = False
        self._sort = "name"
        self._marked = set()
        self._clip = []
        self._clip_cut = False
        self._remember = {}     # dir -> child name to land on
        self._entries = []
        self._parent = []
        self._parent_index = 0
        self._focus_index = 0
        self._rebuild()

    # --- exposed state ---------------------------------------------------

    @Property(str, constant=True)
    def homePath(self):
        return str(Path.home())

    @Property(str, notify=dirChanged)
    def cwd(self):
        return str(self._cwd)

    @Property("QVariantList", notify=dirChanged)
    def entries(self):
        return self._entries

    @Property("QVariantList", notify=dirChanged)
    def parentEntries(self):
        return self._parent

    @Property(int, notify=dirChanged)
    def parentIndex(self):
        return self._parent_index

    @Property(int, notify=dirChanged)
    def focusIndex(self):
        return self._focus_index

    @Property(bool, notify=flagsChanged)
    def showHidden(self):
        return self._show_hidden

    @Property(str, notify=flagsChanged)
    def sortMode(self):
        return self._sort

    @Property(int, notify=clipChanged)
    def clipCount(self):
        return len(self._clip)

    @Property(bool, notify=clipChanged)
    def clipCut(self):
        return self._clip_cut

    @Property(int, notify=dirChanged)
    def markCount(self):
        return len(self._marked)

    # --- listing ---------------------------------------------------------

    def _read(self, directory: Path) -> list:
        try:
            children = list(directory.iterdir())
        except OSError:
            return []
        if not self._show_hidden:
            children = [p for p in children if not p.name.startswith(".")]
        entries = [_entry(p, self._marked) for p in children]
        if self._sort == "size":
            entries.sort(key=lambda e: -e["size"])
        elif self._sort == "time":
            entries.sort(key=lambda e: -e["mtime"])
        else:
            entries.sort(key=lambda e: e["name"].lower())
        entries.sort(key=lambda e: not e["isDir"])  # dirs first, stable
        return entries

    def _rebuild(self):
        self._entries = self._read(self._cwd)
        parent = self._cwd.parent
        if parent != self._cwd:
            self._parent = self._read(parent)
            self._parent_index = next(
                (i for i, e in enumerate(self._parent) if e["path"] == str(self._cwd)), 0)
        else:
            self._parent = []
            self._parent_index = 0
        want = self._remember.get(str(self._cwd))
        self._focus_index = next(
            (i for i, e in enumerate(self._entries) if e["name"] == want), 0)
        self.dirChanged.emit()

    # --- navigation ------------------------------------------------------

    @Slot(str)
    def remember(self, name):
        self._remember[str(self._cwd)] = name

    @Slot(str)
    def enter(self, path):
        p = Path(path)
        if p.is_dir():
            self._cwd = p
            self._rebuild()

    @Slot()
    def leave(self):
        parent = self._cwd.parent
        if parent != self._cwd:
            self._remember[str(parent)] = self._cwd.name
            self._cwd = parent
            self._rebuild()

    @Slot(str)
    def setCwd(self, path):
        p = Path(path).expanduser()
        if p.is_dir():
            self._cwd = p
            self._rebuild()

    @Slot()
    def goHome(self):
        self.setCwd(str(Path.home()))

    @Slot()
    def refresh(self):
        self._rebuild()

    @Slot()
    def toggleHidden(self):
        self._show_hidden = not self._show_hidden
        self.flagsChanged.emit()
        self._rebuild()

    @Slot()
    def cycleSort(self):
        self._sort = {"name": "size", "size": "time", "time": "name"}[self._sort]
        self.flagsChanged.emit()
        self._rebuild()

    # --- preview ---------------------------------------------------------

    @Slot(str, result="QVariantMap")
    def previewFor(self, path):
        if not path:
            return {"type": "empty"}
        p = Path(path)
        if p.is_dir():
            return {"type": "dir", "entries": self._read(p)}
        kind = _kind(p, False, p.is_symlink(), False)
        if kind == "image":
            return {"type": "image", "path": str(p)}
        try:
            st = p.stat()
        except OSError:
            return {"type": "empty"}
        if st.st_size == 0:
            return {"type": "info", "fields": [["size", "empty file"]]}
        try:
            data = p.read_bytes()[:_PREVIEW_BYTES]
        except OSError:
            data = b""
        if b"\0" in data[:8192] or kind in ("video", "audio", "archive"):
            return {"type": "info", "fields": [
                ["type", kind],
                ["size", _human_size(st.st_size)],
                ["modified", _rel_time(st.st_mtime)],
                ["perms", _perms(st.st_mode, False, p.is_symlink())],
            ]}
        text = data.decode("utf-8", "replace")
        return {"type": "text", "text": "\n".join(text.splitlines()[:600])}

    # --- marks -----------------------------------------------------------

    @Slot(str)
    def toggleMark(self, path):
        if path in self._marked:
            self._marked.discard(path)
        else:
            self._marked.add(path)
        self._rebuild()

    @Slot()
    def clearMarks(self):
        if self._marked:
            self._marked.clear()
            self._rebuild()

    def _targets(self, hover):
        return list(self._marked) if self._marked else ([hover] if hover else [])

    # --- operations ------------------------------------------------------

    @Slot(str, bool)
    def yank(self, hover, cut):
        targets = self._targets(hover)
        if not targets:
            return
        self._clip = targets
        self._clip_cut = cut
        self.clipChanged.emit()
        self.notify.emit(f"{'cut' if cut else 'yanked'} {len(targets)} item(s)", False)

    @Slot()
    def paste(self):
        if not self._clip:
            self.notify.emit("nothing to paste", True)
            return
        done = failed = 0
        for src in self._clip:
            src_path = Path(src)
            dst = _dedupe(self._cwd / src_path.name)
            try:
                if self._clip_cut:
                    shutil.move(src, str(dst))
                elif src_path.is_dir():
                    shutil.copytree(src, dst, symlinks=True)
                else:
                    shutil.copy2(src, dst, follow_symlinks=False)
                done += 1
            except OSError:
                failed += 1
        if self._clip_cut:
            self._clip = []
            self.clipChanged.emit()
        self._marked.clear()
        self._rebuild()
        if failed:
            self.notify.emit(f"pasted {done}, {failed} failed", True)
        else:
            self.notify.emit(f"pasted {done} item(s)", False)

    @Slot(str)
    def remove(self, hover):
        targets = self._targets(hover)
        done = failed = 0
        for path in targets:
            p = Path(path)
            try:
                if p.is_dir() and not p.is_symlink():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                done += 1
            except OSError:
                failed += 1
        self._marked.clear()
        self._rebuild()
        if failed:
            self.notify.emit(f"deleted {done}, {failed} failed", True)
        else:
            self.notify.emit(f"deleted {done} item(s)", False)

    @Slot(str, str)
    def rename(self, path, new_name):
        new_name = new_name.strip()
        if not new_name:
            return
        dst = self._cwd / new_name
        try:
            Path(path).rename(dst)
            self._remember[str(self._cwd)] = dst.name
            self._rebuild()
        except OSError as e:
            self.notify.emit(f"rename failed: {e.strerror or e}", True)

    @Slot(str)
    def create(self, text):
        raw = text.strip()
        if not raw:
            return
        is_dir = raw.endswith("/")
        clean = raw.rstrip("/")
        target = self._cwd / clean
        try:
            if is_dir:
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.touch(exist_ok=True)
            self._remember[str(self._cwd)] = clean.split("/")[0]
            self._rebuild()
        except OSError as e:
            self.notify.emit(f"create failed: {e.strerror or e}", True)

    @Slot(str)
    def openPath(self, path):
        try:
            subprocess.Popen(["xdg-open", path], start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except OSError:
            self.notify.emit("no handler for that file", True)

    @Slot()
    def openTerminal(self):
        term = os.environ.get("TERMINAL") or next(
            (t for t in _TERMINALS if shutil.which(t)), None)
        if not term:
            self.notify.emit("no terminal found", True)
            return
        try:
            subprocess.Popen([term], cwd=str(self._cwd), start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except OSError:
            self.notify.emit("couldn't open a terminal", True)

    # --- archives --------------------------------------------------------

    @Slot(str, result=bool)
    def zipShouldPrompt(self, hover):
        return len(self._targets(hover)) > 1

    @Slot(str, result=str)
    def zipDefaultName(self, hover):
        targets = self._targets(hover)
        if len(targets) == 1:
            p = Path(targets[0])
            return p.name if p.is_dir() else (p.stem or p.name)
        return "archive"

    @Slot(str, str)
    def zip(self, hover, name):
        targets = [Path(t) for t in self._targets(hover)]
        if not targets:
            return
        name = (name or "").strip() or "archive"
        if not name.lower().endswith(".zip"):
            name += ".zip"
        dest = _dedupe(self._cwd / name)
        try:
            with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
                if len(targets) == 1 and targets[0].is_dir():
                    _zip_tree(zf, targets[0], Path())      # a lone folder -> its contents
                else:
                    for t in targets:
                        if t.is_dir():
                            _zip_tree(zf, t, Path(t.name))  # keep each folder's name
                        elif t.exists():
                            zf.write(t, t.name)
        except OSError as e:
            self.notify.emit(f"zip failed: {e.strerror or e}", True)
            return
        self._marked.clear()
        self._remember[str(self._cwd)] = dest.name
        self._rebuild()
        self.notify.emit(f"zipped → {dest.name}", False)

    @Slot(str)
    def unzip(self, hover):
        archives = [Path(t) for t in self._targets(hover)
                    if Path(t).is_file() and _archive_stem(Path(t).name)]
        if not archives:
            self.notify.emit("not an archive", True)
            return
        done = failed = 0
        last = None
        for p in archives:
            dest = _dedupe(self._cwd / _archive_stem(p.name))
            try:
                dest.mkdir(parents=True)
                shutil.unpack_archive(str(p), str(dest))
                done += 1
                last = dest.name
            except (OSError, shutil.ReadError, ValueError):
                try:
                    dest.rmdir()
                except OSError:
                    pass
                failed += 1
        if last:
            self._remember[str(self._cwd)] = last
        self._rebuild()
        if done and not failed:
            self.notify.emit(f"unzipped {done} archive(s)", False)
        elif done:
            self.notify.emit(f"unzipped {done}, {failed} failed", True)
        else:
            self.notify.emit("unzip failed", True)
