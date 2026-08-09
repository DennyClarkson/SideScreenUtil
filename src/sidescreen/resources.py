from __future__ import annotations

import sys
from pathlib import Path


def asset_path(name: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / name
    return Path(__file__).resolve().parents[2] / "assets" / name
