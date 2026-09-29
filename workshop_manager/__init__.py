"""Manager Warsztatów — workshop registration and management."""

from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"

try:
    __version__ = _VERSION_FILE.read_text(encoding="utf-8").strip()
except OSError:  # pragma: no cover - VERSION is always shipped with the source and the image
    __version__ = "0.0.0-unknown"
