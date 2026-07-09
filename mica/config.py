import os
from pathlib import Path

CACHE_HOME = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "mica"
LOG_FILE = CACHE_HOME / "mica.log"
