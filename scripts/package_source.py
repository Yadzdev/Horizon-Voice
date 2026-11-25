#!/usr/bin/env python3
"""Create a shareable source ZIP without local secrets, caches, or build residue."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import fnmatch

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)
OUTPUT = DIST / "Horizon-Voice-Source.zip"
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".ruff_cache", ".mypy_cache", ".next", "coverage",
}
EXCLUDED_NAMES = {
    ".env", "horizon_voice.db", "horizon_voice.sqlite3", "tsconfig.tsbuildinfo",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log"}

with ZipFile(OUTPUT, "w", ZIP_DEFLATED, compresslevel=9) as archive:
    for file in ROOT.rglob("*"):
        if not file.is_file() or file == OUTPUT:
            continue
        relative = file.relative_to(ROOT)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if file.name in EXCLUDED_NAMES or file.suffix in EXCLUDED_SUFFIXES:
            continue
        if file.name.startswith(".env") and file.name != ".env.example":
            continue
        if relative.parts[0] == "certs" and file.name != ".gitkeep":
            continue
        if relative.parts[0] == "dist" and file.suffix not in {".mcaddon", ".mcpack"}:
            continue
        archive.write(file, Path("Horizon-Voice") / relative)

print(f"Created {OUTPUT} ({OUTPUT.stat().st_size} bytes)")
