import json
import os
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, QProcess, QTimer, Signal

_FIELDS = "PATH,PKNAME,TYPE,LABEL,FSTYPE,SIZE,MOUNTPOINT,RM,HOTPLUG,TRAN,MODEL,VENDOR"
_USER_MOUNTS = ("/run/media/", "/media/", "/mnt/")
# mounts that are never "a drive you plugged in", even on a hotplug bus
_SYSTEM = {"/", "/boot", "/boot/efi", "/efi", "/home", "/usr", "/var", "[SWAP]"}
_SKIP_FS = {"swap", "crypto_LUKS", "LVM2_member", "linux_raid_member", None, ""}


def _human(n):
    for unit in ("B", "K", "M", "G", "T"):
        if n < 1024 or unit == "T":
            return f"{n:.0f}{unit}" if unit == "B" or n >= 10 else f"{n:.1f}{unit}"
        n /= 1024


def _lsblk():
    try:
        out = subprocess.run(["lsblk", "-J", "-b", "-o", _FIELDS], capture_output=True,
                             text=True, timeout=3).stdout
        return json.loads(out).get("blockdevices", [])
    except (OSError, subprocess.SubprocessError, ValueError):
        return []


def _flatten(devs):
    """(volume, its whole disk) pairs. lsblk only nests children when NAME is
    asked for, so walk PKNAME up to the disk instead of trusting the shape."""
    flat, stack = [], list(devs)
    while stack:
        d = stack.pop()
        flat.append(d)
        stack.extend(d.get("children") or [])
    by_name = {Path(d["path"]).name: d for d in flat if d.get("path")}
    out = []
    for d in flat:
        top, hops = d, 0
        while top.get("pkname") in by_name and hops < 8:
            top, hops = by_name[top["pkname"]], hops + 1
        out.append((d, top))
    return out


def _external(dev, disk):
    mount = dev.get("mountpoint") or ""
    if mount in _SYSTEM:
        return False
    if mount.startswith(_USER_MOUNTS):
        return True
    name = disk.get("path") or ""
    return bool(disk.get("rm") or disk.get("hotplug")
                or disk.get("tran") in ("usb", "ieee1394", "mmc")
                or "/mmcblk" in name)


def list_drives():
    drives = []
    for dev, disk in _flatten(_lsblk()):
        if dev.get("fstype") in _SKIP_FS or not _external(dev, disk):
            continue
        mount = dev.get("mountpoint") or ""
        size = int(dev.get("size") or 0)
        model = " ".join(filter(None, [(disk.get("vendor") or "").strip(),
                                       (disk.get("model") or "").strip()]))
        free = ""
        if mount:
            try:
                free = _human(shutil.disk_usage(mount).free) + " free"
            except OSError:
                pass
        drives.append({
            "dev": dev["path"],
            "disk": disk["path"],
            "name": dev.get("label") or model or Path(dev["path"]).name,
            "fstype": dev.get("fstype") or "",
            "sizeText": _human(size) if size else "",
            "mount": mount,
            "free": free,
            "model": model,
            "bus": disk.get("tran") or "",
            "removable": bool(disk.get("rm") or disk.get("hotplug")),
        })
    drives.sort(key=lambda d: (d["disk"], d["dev"]))
    return drives


class Drives(QObject):
    """Removable / external volumes, kept fresh by watching udev's by-id dir and
    the per-user mount root. Mounting and ejecting go through udisksctl so a
    normal user can do it without sudo."""
    changed = Signal()
    plugged = Signal(str)          # display name of a volume that just appeared
    mounted = Signal(str, str)     # dev, mountpoint — after a mount we asked for
    message = Signal(str, bool)    # text, isError

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drives = list_drives()
        self._procs = set()
        self._timer = QTimer(self, singleShot=True, interval=400)
        self._timer.timeout.connect(self._rescan)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(lambda _: self._timer.start())
        self._watch()

    def _watch(self):
        user = os.environ.get("USER") or Path.home().name
        want = ["/dev/disk/by-id", "/dev/disk/by-uuid", "/run/media", f"/run/media/{user}", "/media"]
        have = set(self._watcher.directories())
        for p in want:
            if p not in have and os.path.isdir(p):
                self._watcher.addPath(p)

    def _rescan(self):
        self._watch()                  # /run/media/$USER only exists after a first mount
        old = {d["dev"] for d in self._drives}
        new = list_drives()
        if new == self._drives:
            return
        self._drives = new
        for d in new:
            if d["dev"] not in old:
                self.plugged.emit(d["name"])
        self.changed.emit()

    def all(self):
        return self._drives

    def find(self, dev):
        return next((d for d in self._drives if d["dev"] == dev), None)

    def owning(self, path):
        """The drive whose mountpoint contains path, if any."""
        p = str(path)
        for d in self._drives:
            m = d["mount"]
            if m and (p == m or p.startswith(m.rstrip("/") + "/")):
                return d
        return None

    def _udisks(self, args, done):
        if not shutil.which("udisksctl"):
            self.message.emit("udisksctl not found — install udisks2", True)
            return
        proc = QProcess(self)
        self._procs.add(proc)

        def finished(code, _status):
            self._procs.discard(proc)
            out = bytes(proc.readAllStandardOutput()).decode(errors="replace").strip()
            err = bytes(proc.readAllStandardError()).decode(errors="replace").strip()
            proc.deleteLater()
            done(code == 0, out, err)

        proc.finished.connect(finished)
        proc.start("udisksctl", args)

    @staticmethod
    def _why(err):
        # udisksctl errors are "Error mounting /dev/x: GDBus.Error:…: <reason>"
        return err.splitlines()[0].rsplit(": ", 1)[-1] if err else "failed"

    def mount(self, dev):
        d = self.find(dev)
        if d and d["mount"]:
            self.mounted.emit(dev, d["mount"])
            return

        def done(ok, _out, err):
            self._rescan()
            d = self.find(dev)
            if ok and d and d["mount"]:
                self.mounted.emit(dev, d["mount"])
            else:
                self.message.emit(f"couldn't mount {dev}: {self._why(err)}", True)

        self.message.emit(f"mounting {d['name'] if d else dev}…", False)
        self._udisks(["mount", "-b", dev], done)

    def eject(self, dev):
        d = self.find(dev)
        if not d:
            return
        name = d["name"]

        def powered(ok, _out, _err):
            self._rescan()
            self.message.emit(f"{name} is safe to unplug" if ok
                              else f"unmounted {name} (couldn't power it off)", not ok)

        def unmounted(ok, _out, err):
            if not ok:
                self._rescan()
                self.message.emit(f"couldn't unmount {name}: {self._why(err)}", True)
                return
            self._rescan()
            # only power the stick off once nothing else on it is still mounted
            if not d["removable"] or any(x["disk"] == d["disk"] and x["mount"] for x in self._drives):
                self.message.emit(f"unmounted {name}", False)
            else:
                self._udisks(["power-off", "-b", d["disk"]], powered)

        if d["mount"]:
            self._udisks(["unmount", "-b", dev], unmounted)
        else:
            unmounted(True, "", "")
