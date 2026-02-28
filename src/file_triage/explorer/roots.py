"""
Determine filesystem roots for navigation (e.g. /, /Volumes/MyDisk on macOS).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def get_roots() -> list[Path]:
    """
    Return list of root paths the user can navigate from (read-only).
    macOS: / and each volume under /Volumes (not /Volumes itself). Sorted case-insensitively by path.
    """
    roots: list[Path] = []
    if sys.platform == "darwin":
        roots.append(Path("/").resolve())
        volumes = Path("/Volumes")
        if volumes.is_dir():
            try:
                children = [
                    p.resolve()
                    for p in volumes.iterdir()
                    if p.is_dir() and not p.name.startswith(".")
                ]
                for p in children:
                    try:
                        if p != Path("/"):
                            roots.append(p)
                    except OSError:
                        pass
                roots[1:] = sorted(roots[1:], key=lambda r: str(r).lower())
            except OSError:
                pass
    elif sys.platform == "win32":
        # Windows: drive letters
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            d = Path(f"{letter}:\\")
            if d.exists():
                roots.append(d.resolve())
        if not roots:
            roots.append(Path(os.path.expanduser("~")).resolve())
    else:
        # Linux etc.: / and optionally /mnt
        roots.append(Path("/").resolve())
        mnt = Path("/mnt")
        if mnt.is_dir():
            try:
                for p in sorted(mnt.iterdir()):
                    if p.is_dir():
                        try:
                            roots.append(p.resolve())
                        except OSError:
                            pass
            except OSError:
                pass
    return roots


def is_path_allowed(path: Path, roots: list[Path]) -> bool:
    """True if path is under one of the allowed roots (resolved)."""
    try:
        resolved = path.resolve()
    except OSError:
        return False
    resolved_str = str(resolved)
    for root in roots:
        try:
            root_resolved = root.resolve()
            root_str = str(root_resolved).rstrip(os.sep) or os.sep
            prefix = root_str if root_str == os.sep else root_str + os.sep
            if resolved_str == root_str or resolved_str.startswith(prefix):
                return True
        except OSError:
            continue
    return False
