from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
MEDIA_DIR = ROOT / "Media"
ENTRYPOINT = ROOT / "Pngtuber player.py"
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
ICON_ICO_SOURCE = MEDIA_DIR / "Icon.ico"
ICON_PNG_SOURCE = MEDIA_DIR / "Icon.png"
ICON_ICO_FALLBACK = BUILD_DIR / "PocketRT.ico"


def ensure_icon() -> Path:
    if ICON_ICO_SOURCE.exists():
        return ICON_ICO_SOURCE

    BUILD_DIR.mkdir(exist_ok=True)
    if not ICON_PNG_SOURCE.exists():
        raise FileNotFoundError(
            f"Missing icon source: {ICON_ICO_SOURCE} or {ICON_PNG_SOURCE}"
        )

    image = Image.open(ICON_PNG_SOURCE).convert("RGBA")
    image.save(
        ICON_ICO_FALLBACK,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    return ICON_ICO_FALLBACK


def main() -> int:
    icon_path = ensure_icon()

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--noconsole",
        "--name",
        "PocketRT",
        "--icon",
        str(icon_path),
        "--add-data",
        f"{MEDIA_DIR}{os.pathsep}Media",
        str(ENTRYPOINT),
    ]

    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
