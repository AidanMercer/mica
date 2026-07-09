import configparser
import os
import shutil
import subprocess
from pathlib import Path


def _app_dirs():
    dirs = [Path.home() / ".local/share/applications"]
    data_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
    dirs += [Path(d) / "applications" for d in data_dirs.split(":") if d]
    return dirs


def _query(*args):
    try:
        return subprocess.run(["xdg-mime", *args], capture_output=True,
                              text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _gio_ids(mime):
    """Desktop ids gio associates with a mime (reads the mimeapps cache, which
    is fuller than scanning MimeType= lines). Locale-proof: only picks tokens
    that end in .desktop, so translated headers don't matter."""
    try:
        out = subprocess.run(["gio", "mime", mime], capture_output=True,
                             text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    ids = []
    for line in out.splitlines():
        tok = line.strip()
        tok = tok.split(":")[-1].strip() if ":" in tok else tok
        if tok.endswith(".desktop") and tok not in ids:
            ids.append(tok)
    return ids


def _read_desktop(path):
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        cp.read(path, encoding="utf-8")
    except (OSError, configparser.Error):
        return None
    if not cp.has_section("Desktop Entry"):
        return None
    e = cp["Desktop Entry"]
    if e.get("Type") != "Application":
        return None
    if e.get("NoDisplay", "false").lower() == "true" or e.get("Hidden", "false").lower() == "true":
        return None
    return {"id": path.name, "path": str(path), "name": e.get("Name", path.stem)}


def apps_for(filepath):
    """Apps to open filepath: its default, then the rest registered for its mime,
    then every other installed app (so you can always pick something). Shaped for
    QML with isDefault / recommended flags."""
    mime = _query("query", "filetype", str(filepath))
    default = _query("query", "default", mime) if mime else ""

    seen = {}
    for d in _app_dirs():
        if not d.is_dir():
            continue
        for f in d.glob("*.desktop"):
            if f.name not in seen:
                info = _read_desktop(f)
                if info is not None:
                    seen[f.name] = info

    order = []
    def add(i):
        if i in seen and i not in order:
            order.append(i)

    add(default)
    for i in _gio_ids(mime):
        add(i)
    rec = len(order)                       # everything before here is recommended
    for a in sorted(seen.values(), key=lambda a: a["name"].lower()):
        add(a["id"])

    return [{"name": seen[i]["name"], "id": i, "path": seen[i]["path"],
             "isDefault": i == default, "recommended": idx < rec}
            for idx, i in enumerate(order)]


def launch(desktop_path, filepath):
    tool = (["gio", "launch", desktop_path, str(filepath)] if shutil.which("gio")
            else ["gtk-launch", Path(desktop_path).stem, str(filepath)]
            if shutil.which("gtk-launch") else None)
    if tool is None:
        return False
    try:
        subprocess.Popen(tool, start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False
