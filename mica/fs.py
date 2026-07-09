import os
import shutil
import stat
import subprocess
import tarfile
import time
import urllib.parse
import zipfile
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (Property, QObject, QRunnable, QThreadPool, Signal,
                            Slot)

from .thumbs import Thumbnailer

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


def _archive_listing(path: Path):
    """Top-level entries inside a zip/tar, shaped like dir entries so the preview
    pane can list them without extracting. None if it can't be read."""
    raw = []
    try:
        if path.name.lower().endswith(".zip"):
            with zipfile.ZipFile(path) as z:
                for info in z.infolist()[:2000]:
                    raw.append((info.filename, info.file_size, info.is_dir()))
        else:
            with tarfile.open(path) as t:
                for member in t:
                    raw.append((member.name, member.size, member.isdir()))
                    if len(raw) >= 2000:
                        break
    except (OSError, tarfile.TarError, zipfile.BadZipFile, EOFError):
        return None

    top = {}
    for name, size, is_dir in raw:
        parts = name.strip("/").split("/")
        if not parts or not parts[0]:
            continue
        entry = top.setdefault(parts[0], {"is_dir": False, "size": 0})
        if len(parts) > 1 or is_dir:
            entry["is_dir"] = True
        else:
            entry["size"] += size

    entries = [{
        "name": name,
        "path": "",
        "isDir": e["is_dir"],
        "isLink": False,
        "size": e["size"],
        "sizeText": "" if e["is_dir"] else _human_size(e["size"]),
        "mtimeText": "",
        "perms": "",
        "marked": False,
        "kind": "dir" if e["is_dir"] else _kind(Path(name), False, False, False),
    } for name, e in top.items()]
    entries.sort(key=lambda x: x["name"].lower())
    entries.sort(key=lambda x: not x["isDir"])
    return entries


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


class _OpSignals(QObject):
    progress = Signal(int, int, str)   # done, total, verb
    done = Signal(object)              # result dict


class _OpJob(QRunnable):
    """Runs a file-op function on a pool thread and reports back through
    _OpSignals, so a big copy/delete/zip never blocks the UI."""
    def __init__(self, fn, signals):
        super().__init__()
        self._fn = fn
        self._signals = signals

    def run(self):
        try:
            res = self._fn(self._signals)
        except Exception as e:      # surface any failure as a toast
            res = {"error": str(e)}
        self._signals.done.emit(res)


def _trash(path: Path):
    """Move a file into the XDG trash so a delete is recoverable. The .trashinfo
    record is written before the move, per the freedesktop spec."""
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    files_dir = data_home / "Trash" / "files"
    info_dir = data_home / "Trash" / "info"
    files_dir.mkdir(parents=True, exist_ok=True)
    info_dir.mkdir(parents=True, exist_ok=True)
    name = path.name
    i = 1
    while (files_dir / name).exists() or (info_dir / f"{name}.trashinfo").exists():
        name = f"{path.name}.{i}"
        i += 1
    quoted = urllib.parse.quote(os.path.abspath(path), safe="/")
    stamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    (info_dir / f"{name}.trashinfo").write_text(
        f"[Trash Info]\nPath={quoted}\nDeletionDate={stamp}\n")
    shutil.move(str(path), str(files_dir / name))


def _trashinfo(files_path: Path):
    """The .trashinfo file that goes with a trashed item, or None."""
    info = files_path.parent.parent / "info" / f"{files_path.name}.trashinfo"
    return info if info.exists() else None


def _restore_one(files_path: Path):
    info = _trashinfo(files_path)
    origin = None
    if info is not None:
        for line in info.read_text().splitlines():
            if line.startswith("Path="):
                origin = Path(urllib.parse.unquote(line[5:]))
                break
    if origin is None:
        raise OSError("no trash record")
    dest = _dedupe(origin)                    # don't clobber whatever's there now
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(files_path), str(dest))
    info.unlink(missing_ok=True)
    return dest


class Fs(QObject):
    dirChanged = Signal()      # cwd / entries / parent changed
    flagsChanged = Signal()    # hidden or sort
    clipChanged = Signal()
    notify = Signal(str, bool)  # message, isError
    thumbReady = Signal(str, str)  # source path, thumbnail path
    progress = Signal(int, int, str)  # done, total, verb — a "" verb clears it

    def __init__(self, start: Path, parent=None):
        super().__init__(parent)
        self._thumbs = Thumbnailer(self)
        self._thumbs.ready.connect(self.thumbReady)
        self._busy = False
        self._op_sig = None
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
        self._search_index = []
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
    def goTrash(self):
        data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
        files = data_home / "Trash" / "files"
        if files.is_dir():
            self.setCwd(str(files))
        else:
            self.notify.emit("trash is empty", False)

    @Slot(str)
    def jumpTo(self, path):
        p = Path(path)
        parent = p.parent
        if parent.is_dir():
            self._remember[str(parent)] = p.name
            self._cwd = parent
            self._rebuild()

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
        ext = p.suffix.lower()
        if kind in ("video", "audio") or ext == ".pdf":
            thumb = self._thumbs.get(p, "pdf" if ext == ".pdf" else kind)
            if thumb:
                return {"type": "image", "path": thumb}
            # fall through to the info card while the thumbnail renders
        if _archive_stem(p.name):
            listing = _archive_listing(p)
            if listing is not None:
                return {"type": "dir", "entries": listing}
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

    # --- search ----------------------------------------------------------

    @Slot()
    def beginSearch(self):
        """Index the tree under cwd once (capped), so keystrokes can filter it in
        memory instead of re-walking the disk each time."""
        base = self._cwd
        index = []
        scanned = 0
        for root, dirs, files in os.walk(base):
            if not self._show_hidden:
                dirs[:] = [d for d in dirs if not d.startswith(".")]
            root_p = Path(root)
            names = [n for n in dirs + files if self._show_hidden or not n.startswith(".")]
            for name in names:
                scanned += 1
                p = root_p / name
                index.append((name.lower(), str(p.relative_to(base)), str(p)))
                if len(index) >= 50000:
                    self._search_index = index
                    return
            if scanned >= 50000:
                break
        self._search_index = index

    @Slot(str, result="QVariantList")
    def search(self, query):
        q = query.strip().lower()
        if not q:
            return []
        out = []
        for name_l, rel, path in self._search_index:
            if q in name_l:
                entry = _entry(Path(path), self._marked)
                entry["rel"] = rel
                out.append(entry)
                if len(out) >= 500:
                    break
        return out

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

    # --- background jobs -------------------------------------------------

    def _run_op(self, job, finalize):
        if self._busy:
            self.notify.emit("busy — let the current job finish", True)
            return
        self._busy = True
        sig = _OpSignals()
        self._op_sig = sig                        # keep a ref until it finishes
        sig.progress.connect(self._on_progress)
        sig.done.connect(lambda res: self._finish_op(res, finalize))
        QThreadPool.globalInstance().start(_OpJob(job, sig))

    def _on_progress(self, done, total, verb):
        self.progress.emit(done, total, verb)

    def _finish_op(self, res, finalize):
        self._busy = False
        self._op_sig = None
        self.progress.emit(0, 0, "")
        if isinstance(res, dict) and res.get("error"):
            self._rebuild()
            self.notify.emit(f"failed: {res['error']}", True)
        else:
            finalize(res)

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
        sources = [Path(s) for s in self._clip]
        cut = self._clip_cut
        cwd = self._cwd
        verb = "moving" if cut else "copying"
        total = len(sources)

        def job(sig):
            ok = failed = 0
            for i, src in enumerate(sources):
                sig.progress.emit(i + 1, total, verb)
                dst = _dedupe(cwd / src.name)
                try:
                    if cut:
                        shutil.move(str(src), str(dst))
                    elif src.is_dir():
                        shutil.copytree(src, dst, symlinks=True)
                    else:
                        shutil.copy2(src, dst, follow_symlinks=False)
                    ok += 1
                except OSError:
                    failed += 1
            return {"ok": ok, "failed": failed, "cut": cut}

        def finalize(res):
            if res["cut"]:
                self._clip = []
                self.clipChanged.emit()
            self._marked.clear()
            self._rebuild()
            self._report(res, "pasted")

        self._run_op(job, finalize)

    @Slot(str)
    def trash(self, hover):
        targets = [Path(t) for t in self._targets(hover)]
        if not targets:
            return
        total = len(targets)

        def job(sig):
            ok = failed = 0
            for i, p in enumerate(targets):
                sig.progress.emit(i + 1, total, "trashing")
                try:
                    _trash(p)
                    ok += 1
                except OSError:
                    failed += 1
            return {"ok": ok, "failed": failed}

        def finalize(res):
            self._marked.clear()
            self._rebuild()
            self._report(res, "trashed")

        self._run_op(job, finalize)

    @Slot(str)
    def remove(self, hover):
        targets = [Path(t) for t in self._targets(hover)]
        if not targets:
            return
        total = len(targets)

        def job(sig):
            ok = failed = 0
            for i, p in enumerate(targets):
                sig.progress.emit(i + 1, total, "deleting")
                try:
                    if p.is_dir() and not p.is_symlink():
                        shutil.rmtree(p)
                    else:
                        p.unlink()
                    ok += 1
                except OSError:
                    failed += 1
            return {"ok": ok, "failed": failed}

        def finalize(res):
            self._marked.clear()
            self._rebuild()
            self._report(res, "deleted")

        self._run_op(job, finalize)

    def _report(self, res, verb):
        if res["failed"]:
            self.notify.emit(f"{verb} {res['ok']}, {res['failed']} failed", True)
        else:
            self.notify.emit(f"{verb} {res['ok']} item(s)", False)

    @Slot(str, result=bool)
    def canRestore(self, hover):
        return any(_trashinfo(Path(t)) for t in self._targets(hover))

    @Slot(str)
    def restore(self, hover):
        items = [Path(t) for t in self._targets(hover) if _trashinfo(Path(t))]
        if not items:
            self.notify.emit("nothing to restore", True)
            return
        total = len(items)

        def job(sig):
            ok = failed = 0
            for i, p in enumerate(items):
                sig.progress.emit(i + 1, total, "restoring")
                try:
                    _restore_one(p)
                    ok += 1
                except OSError:
                    failed += 1
            return {"ok": ok, "failed": failed}

        def finalize(res):
            self._marked.clear()
            self._rebuild()
            self._report(res, "restored")

        self._run_op(job, finalize)

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
        lone_dir = len(targets) == 1 and targets[0].is_dir()
        total = len(targets)

        def job(sig):
            with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
                if lone_dir:
                    sig.progress.emit(1, 1, "zipping")
                    _zip_tree(zf, targets[0], Path())       # a lone folder -> its contents
                else:
                    for i, t in enumerate(targets):
                        sig.progress.emit(i + 1, total, "zipping")
                        if t.is_dir():
                            _zip_tree(zf, t, Path(t.name))   # keep each folder's name
                        elif t.exists():
                            zf.write(t, t.name)
            return {"dest": dest.name}

        def finalize(res):
            self._marked.clear()
            self._remember[str(self._cwd)] = res["dest"]
            self._rebuild()
            self.notify.emit(f"zipped → {res['dest']}", False)

        self._run_op(job, finalize)

    @Slot(str)
    def unzip(self, hover):
        archives = [Path(t) for t in self._targets(hover)
                    if Path(t).is_file() and _archive_stem(Path(t).name)]
        if not archives:
            self.notify.emit("not an archive", True)
            return
        cwd = self._cwd
        total = len(archives)

        def job(sig):
            ok = failed = 0
            last = None
            for i, p in enumerate(archives):
                sig.progress.emit(i + 1, total, "extracting")
                dest = _dedupe(cwd / _archive_stem(p.name))
                try:
                    dest.mkdir(parents=True)
                    shutil.unpack_archive(str(p), str(dest))
                    ok += 1
                    last = dest.name
                except (OSError, shutil.ReadError, ValueError):
                    try:
                        dest.rmdir()
                    except OSError:
                        pass
                    failed += 1
            return {"ok": ok, "failed": failed, "last": last}

        def finalize(res):
            if res["last"]:
                self._remember[str(self._cwd)] = res["last"]
            self._rebuild()
            if res["ok"] and not res["failed"]:
                self.notify.emit(f"unzipped {res['ok']} archive(s)", False)
            elif res["ok"]:
                self.notify.emit(f"unzipped {res['ok']}, {res['failed']} failed", True)
            else:
                self.notify.emit("unzip failed", True)

        self._run_op(job, finalize)
