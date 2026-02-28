"""
Directory scanning and inventory.

Scans one or more roots and collects basic file/folder info (path, size, mtime, etc.)
as a foundation for later analysis (duplicates, by-date, by-type) and organisation.
"""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator


@dataclass
class FileEntry:
    """A single file or directory in the inventory."""

    path: Path
    name: str
    is_dir: bool
    size_bytes: int
    mtime: datetime | None
    # Optional: add checksum later for dedup

    def __post_init__(self) -> None:
        if isinstance(self.path, str):
            self.path = Path(self.path)
        if self.mtime is not None and isinstance(self.mtime, (int, float)):
            self.mtime = datetime.fromtimestamp(self.mtime)


def scan_root(root: Path | str, *, follow_symlinks: bool = False) -> Iterator[FileEntry]:
    """
    Walk a directory tree and yield FileEntry for each file and directory.

    Use follow_symlinks=False to avoid following symlinks into other disks/trees.
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(str(root))

    for entry in os.scandir(root):
        try:
            path = Path(entry.path)
            stat = entry.stat(follow_symlinks=follow_symlinks)
            is_dir = entry.is_dir(follow_symlinks=follow_symlinks)
            yield FileEntry(
                path=path,
                name=entry.name,
                is_dir=is_dir,
                size_bytes=stat.st_size if not is_dir else 0,
                mtime=datetime.fromtimestamp(stat.st_mtime) if stat.st_mtime else None,
            )
        except OSError:
            continue  # skip permission errors etc.

    for entry in os.scandir(root):
        if entry.is_dir(follow_symlinks=follow_symlinks):
            try:
                sub = Path(entry.path)
                yield from scan_root(sub, follow_symlinks=follow_symlinks)
            except OSError:
                continue


def scan_roots(
    roots: list[Path | str], *, follow_symlinks: bool = False
) -> Iterator[FileEntry]:
    """Scan multiple roots (e.g. multiple mount points) and yield all entries."""
    for root in roots:
        yield from scan_root(root, follow_symlinks=follow_symlinks)
