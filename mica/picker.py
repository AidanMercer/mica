from pathlib import Path

from PySide6.QtCore import Property, QObject, Slot


class Picker(QObject):
    """File-picker session for --pick mode. When mica runs as an
    xdg-desktop-portal file chooser, QML calls choose()/cancel() here; we write
    the selected paths (one per line, absolute) to the out file the portal gave
    us and quit. An empty/absent out file means the user cancelled."""

    def __init__(self, app, opts, parent=None):
        super().__init__(parent)
        self._app = app
        self._out = opts.get("out", "")
        self._multiple = bool(opts.get("multiple"))
        self._directory = bool(opts.get("directory"))
        self._save = bool(opts.get("save"))
        self._name = opts.get("name", "")

    @Property(bool, constant=True)
    def multiple(self):
        return self._multiple

    @Property(bool, constant=True)
    def directory(self):
        return self._directory

    @Property(bool, constant=True)
    def save(self):
        return self._save

    @Property(str, constant=True)
    def suggestedName(self):
        return self._name

    def _write(self, paths):
        if not self._out:
            return
        try:
            Path(self._out).write_text("".join(p + "\n" for p in paths))
        except OSError:
            pass

    @Slot("QStringList")
    def choose(self, paths):
        paths = [p for p in paths if p]
        if not paths:
            return
        self._write(paths)
        self._app.quit()

    @Slot(str)
    def chooseOne(self, path):
        self.choose([path])

    @Slot()
    def cancel(self):
        self._write([])
        self._app.quit()
