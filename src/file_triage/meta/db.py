"""
SQLite schema and access for the meta overlay.

Schema:
  meta: one row per path that has metadata (path PK, inode, device, updated_at, vpath)
  vpath: when set, item is "moved" to that location for display (no filesystem change)

Only paths that have at least one tag (or other metadata) have a meta row.
"""

from __future__ import annotations

import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _path_key(path: str | Path) -> str:
    """Return the key string for meta lookups: UUID as-is, else resolved path."""
    s = str(path).strip()
    if not s:
        return s
    try:
        uuid.UUID(s)
        return s
    except (ValueError, TypeError):
        pass
    return str(Path(path).resolve())


_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    path TEXT PRIMARY KEY,
    inode INTEGER,
    device INTEGER,
    updated_at TEXT NOT NULL,
    vpath TEXT
);

CREATE TABLE IF NOT EXISTS tags (
    path TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (path, tag),
    FOREIGN KEY (path) REFERENCES meta(path) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS tags_path ON tags(path);
CREATE INDEX IF NOT EXISTS tags_tag ON tags(tag);

CREATE TABLE IF NOT EXISTS name_rule_tags (
    pattern TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (pattern, tag)
);

CREATE INDEX IF NOT EXISTS name_rule_tags_pattern ON name_rule_tags(pattern);
CREATE INDEX IF NOT EXISTS name_rule_tags_tag ON name_rule_tags(tag);

CREATE TABLE IF NOT EXISTS tag_nulls (
    path TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (path, tag)
);

CREATE INDEX IF NOT EXISTS tag_nulls_path ON tag_nulls(path);
CREATE INDEX IF NOT EXISTS tag_nulls_tag ON tag_nulls(tag);

CREATE TABLE IF NOT EXISTS hidden_tags (
    tag TEXT PRIMARY KEY
);

CREATE INDEX IF NOT EXISTS hidden_tags_tag ON hidden_tags(tag);
"""


def _conn(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    """Create or ensure the meta overlay schema exists."""
    conn = _conn(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
        # Migration: add vpath column if missing (existing DBs)
        cur = conn.execute("PRAGMA table_info(meta)")
        columns = [row[1] for row in cur.fetchall()]
        if "vpath" not in columns:
            conn.execute("ALTER TABLE meta ADD COLUMN vpath TEXT")
            conn.commit()
        # Uniqueness: no two rows may share the same non-null vpath
        cur = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name='meta_vpath_unique'"
        )
        if cur.fetchone() is None:
            conn.execute(
                "CREATE UNIQUE INDEX meta_vpath_unique ON meta(vpath) WHERE vpath IS NOT NULL"
            )
            conn.commit()
        # Migration: rename tag 'trash' to 'hide' (trash is now vpath-based)
        conn.execute("UPDATE tags SET tag = 'hide' WHERE tag = 'trash'")
        conn.execute("UPDATE tag_nulls SET tag = 'hide' WHERE tag = 'trash'")
        conn.commit()
    finally:
        conn.close()


def _path_stat(path: Path) -> tuple[int | None, int | None]:
    """Return (inode, device) for path if it exists; else (None, None)."""
    try:
        st = path.resolve().stat()
        return (st.st_ino, st.st_dev)
    except OSError:
        return (None, None)


# SQLite INTEGER is signed 64-bit; some filesystems return larger inode/device
_SQLITE_INT_MAX = 0x7FFF_FFFF_FFFF_FFFF
_SQLITE_INT_MIN = -0x8000_0000_0000_0000


def _to_sqlite_int(v: int | None) -> int | None:
    """Return v if it fits in SQLite INTEGER; else None to avoid OverflowError."""
    if v is None:
        return None
    if _SQLITE_INT_MIN <= v <= _SQLITE_INT_MAX:
        return v
    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_tag(db_path: Path, path: str | Path, tag: str) -> None:
    """Add a tag to a file or folder. Creates meta row with current inode/device if needed.
    If the tag was in tag_nulls, it is removed so hard and null for the same tag never coexist."""
    path_str = str(Path(path).resolve())
    tag = tag.strip()
    if not tag:
        return
    inode, device = _path_stat(Path(path_str))
    inode = _to_sqlite_int(inode)
    device = _to_sqlite_int(device)
    existing = get_path_meta(db_path, path_str)
    vpath = existing.get("vpath") if existing else None
    conn = _conn(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO meta (path, inode, device, updated_at, vpath) VALUES (?, ?, ?, ?, ?)",
            (path_str, inode, device, _now(), vpath),
        )
        conn.execute("DELETE FROM tag_nulls WHERE path = ? AND tag = ?", (path_str, tag))
        conn.execute("INSERT OR IGNORE INTO tags (path, tag) VALUES (?, ?)", (path_str, tag))
        conn.commit()
    finally:
        conn.close()


def remove_tag(db_path: Path, path: str | Path, tag: str) -> None:
    """Remove a tag from a path. Removes meta row if no tags remain."""
    path_str = str(Path(path).resolve())
    tag = tag.strip()
    conn = _conn(db_path)
    try:
        conn.execute("DELETE FROM tags WHERE path = ? AND tag = ?", (path_str, tag))
        cur = conn.execute("SELECT 1 FROM tags WHERE path = ? LIMIT 1", (path_str,))
        if cur.fetchone() is None:
            conn.execute("DELETE FROM meta WHERE path = ?", (path_str,))
        conn.commit()
    finally:
        conn.close()


def get_tags(db_path: Path, path: str | Path) -> list[str]:
    """Return list of tags for the given path (empty if no metadata)."""
    path_str = str(Path(path).resolve())
    conn = _conn(db_path)
    try:
        cur = conn.execute("SELECT tag FROM tags WHERE path = ? ORDER BY tag", (path_str,))
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def get_all_tagged_paths(db_path: Path) -> list[str]:
    """Return all paths that have at least one tag."""
    conn = _conn(db_path)
    try:
        cur = conn.execute("SELECT DISTINCT path FROM tags ORDER BY path")
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def get_all_tags(db_path: Path) -> list[str]:
    """Return all distinct tag names, sorted."""
    conn = _conn(db_path)
    try:
        cur = conn.execute("SELECT DISTINCT tag FROM tags ORDER BY tag")
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def get_paths_by_tag(db_path: Path, tag: str) -> list[str]:
    """Return all paths that have the given tag."""
    conn = _conn(db_path)
    try:
        cur = conn.execute("SELECT path FROM tags WHERE tag = ? ORDER BY path", (tag.strip(),))
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def get_tag_nulls(db_path: Path, path: str | Path) -> list[str]:
    """Return list of tags that are nullified (not tagged with) for this path."""
    path_str = str(Path(path).resolve())
    conn = _conn(db_path)
    try:
        cur = conn.execute("SELECT tag FROM tag_nulls WHERE path = ? ORDER BY tag", (path_str,))
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def get_paths_by_tag_null(db_path: Path, tag: str) -> list[str]:
    """Return all paths that have the given tag as a null (explicitly negated)."""
    conn = _conn(db_path)
    try:
        cur = conn.execute("SELECT path FROM tag_nulls WHERE tag = ? ORDER BY path", (tag.strip(),))
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def get_hidden_tags(db_path: Path) -> list[str]:
    """Return list of tag names that are hidden (invisible filter)."""
    conn = _conn(db_path)
    try:
        cur = conn.execute("SELECT tag FROM hidden_tags ORDER BY tag")
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def add_hidden_tag(db_path: Path, tag: str) -> None:
    """Mark a tag as hidden (filter out paths with this tag from listings)."""
    tag = tag.strip()
    if not tag:
        return
    conn = _conn(db_path)
    try:
        conn.execute("INSERT OR IGNORE INTO hidden_tags (tag) VALUES (?)", (tag,))
        conn.commit()
    finally:
        conn.close()


def remove_hidden_tag(db_path: Path, tag: str) -> None:
    """Mark a tag as visible (include paths with this tag again)."""
    tag = tag.strip()
    if not tag:
        return
    conn = _conn(db_path)
    try:
        conn.execute("DELETE FROM hidden_tags WHERE tag = ?", (tag,))
        conn.commit()
    finally:
        conn.close()


def add_tag_null(db_path: Path, path: str | Path, tag: str) -> None:
    """Set a null tag (not tagged with) for this path. Removes the tag from tags if present."""
    path_str = str(Path(path).resolve())
    tag = tag.strip()
    if not tag:
        return
    conn = _conn(db_path)
    try:
        conn.execute("DELETE FROM tags WHERE path = ? AND tag = ?", (path_str, tag))
        cur = conn.execute("SELECT 1 FROM tags WHERE path = ? LIMIT 1", (path_str,))
        if cur.fetchone() is None:
            conn.execute("DELETE FROM meta WHERE path = ?", (path_str,))
        conn.execute("INSERT OR REPLACE INTO tag_nulls (path, tag) VALUES (?, ?)", (path_str, tag))
        conn.commit()
    finally:
        conn.close()


def remove_tag_null(db_path: Path, path: str | Path, tag: str) -> None:
    """Remove a null tag and add it as a hard tag (flip null → hard)."""
    path_str = str(Path(path).resolve())
    tag = tag.strip()
    if not tag:
        return
    existing = get_path_meta(db_path, path_str)
    vpath = existing.get("vpath") if existing else None
    conn = _conn(db_path)
    try:
        conn.execute("DELETE FROM tag_nulls WHERE path = ? AND tag = ?", (path_str, tag))
        inode, device = _path_stat(Path(path_str))
        inode = _to_sqlite_int(inode)
        device = _to_sqlite_int(device)
        conn.execute(
            "INSERT OR REPLACE INTO meta (path, inode, device, updated_at, vpath) VALUES (?, ?, ?, ?, ?)",
            (path_str, inode, device, _now(), vpath),
        )
        conn.execute("INSERT OR IGNORE INTO tags (path, tag) VALUES (?, ?)", (path_str, tag))
        conn.commit()
    finally:
        conn.close()


def add_virtual_folder(db_path: Path, vpath_display: str | Path) -> str:
    """Create a meta row for a new virtual folder (no physical origin).
    path is set to a UUID; vpath is set to the display path. Returns the path (UUID).
    Raises ValueError if a meta row already has this vpath (duplicate folder name)."""
    path_str = str(uuid.uuid4())
    vpath_str = str(Path(vpath_display).resolve())
    conn = _conn(db_path)
    try:
        cur = conn.execute("SELECT 1 FROM meta WHERE vpath = ?", (vpath_str,))
        if cur.fetchone() is not None:
            raise ValueError("A folder with this name already exists here")
        conn.execute(
            "INSERT INTO meta (path, inode, device, updated_at, vpath) VALUES (?, ?, ?, ?, ?)",
            (path_str, None, None, _now(), vpath_str),
        )
        conn.commit()
        return path_str
    finally:
        conn.close()


def _scope_key(scope_path: str | Path) -> Path:
    """Normalize a scope/parent path for hierarchy comparison. Do NOT resolve() so that
    vpath strings (e.g. /Users/test5) match DB values on macOS where resolve() could
    return /private/Users/test5. Also normalizes /private/Users -> /Users so stored
    vpaths (from resolve()) match request scope."""
    s = str(scope_path).strip().rstrip("/").rstrip(os.sep)
    if not s:
        return Path("/")
    # macOS: /private/Users is the real path for /Users; normalize so scope matches either form
    if s.startswith("/private/Users"):
        s = "/Users" + s[len("/private/Users"):]
    return Path(s)


def get_virtual_children(db_path: Path, parent_path: str | Path) -> list[str]:
    """Return meta path values for direct virtual children of parent_path.
    Includes rows where inode IS NULL and (path's parent = parent OR vpath's parent = parent)."""
    parent_p = _scope_key(parent_path)
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            "SELECT path, vpath FROM meta WHERE inode IS NULL",
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    result = []
    for path_val, vpath_val in rows:
        if path_val is None:
            continue
        # Legacy: path is the display path (path's parent = parent)
        if _scope_key(Path(path_val).parent) == parent_p:
            result.append(path_val)
            continue
        # New: vpath is the display path (vpath's parent = parent)
        if vpath_val and _scope_key(Path(vpath_val).parent) == parent_p:
            result.append(path_val)
    return result


def set_vpath(db_path: Path, path: str | Path, vpath: str | Path | None) -> None:
    """Set the virtual path (display location) for a path. No filesystem change.
    If the path has no meta row, one is created. vpath=None clears the move.
    If vpath equals path (after normalization), vpath is nullified to avoid duplicate listings.
    Raises ValueError if another row already has this vpath (duplicate folder name).
    Stores vpath with _scope_key (no resolve) so listing by vpath works when path doesn't exist on disk."""
    path_str = _path_key(path)
    vpath_str = str(_scope_key(vpath)) if vpath else None
    if vpath_str and vpath_str == path_str:
        vpath_str = None
    conn = _conn(db_path)
    try:
        if vpath_str:
            cur = conn.execute(
                "SELECT 1 FROM meta WHERE vpath = ? AND path != ?",
                (vpath_str, path_str),
            )
            if cur.fetchone() is not None:
                raise ValueError("A folder with this name already exists there")
        cur = conn.execute("SELECT 1 FROM meta WHERE path = ?", (path_str,))
        if cur.fetchone() is None:
            try:
                inode, device = _path_stat(Path(path_str))
            except Exception:
                inode, device = None, None
            inode = _to_sqlite_int(inode) if inode is not None else None
            device = _to_sqlite_int(device) if device is not None else None
            conn.execute(
                "INSERT INTO meta (path, inode, device, updated_at, vpath) VALUES (?, ?, ?, ?, ?)",
                (path_str, inode, device, _now(), vpath_str),
            )
        else:
            conn.execute(
                "UPDATE meta SET vpath = ?, updated_at = ? WHERE path = ?",
                (vpath_str, _now(), path_str),
            )
        conn.commit()
    finally:
        conn.close()


def get_entries_by_vpath_parent(db_path: Path, parent_path: str | Path) -> list[dict]:
    """Return meta rows where vpath is a direct child of parent_path (vpath IS NOT NULL).
    Each dict: path, vpath (the display path). Uses _scope_key so vpath scope matches on macOS
    and stored vpaths (e.g. /private/Users/...) match request scope (e.g. /Users/...)."""
    parent_p = _scope_key(parent_path)
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            "SELECT path, vpath FROM meta WHERE vpath IS NOT NULL",
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {"path": row[0], "vpath": row[1]}
        for row in rows
        if row[1] and _scope_key(Path(row[1]).parent) == parent_p
    ]


def get_meta_by_vpath(db_path: Path, vpath: str | Path) -> Optional[dict]:
    """Return meta row where vpath equals the given vpath (for lookup by display path).
    Uses _scope_key so lookup works when the vpath does not exist on disk (no resolve())."""
    vpath_str = str(_scope_key(vpath))
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            "SELECT path, inode, device, updated_at, vpath FROM meta WHERE vpath = ?",
            (vpath_str,),
        )
        row = cur.fetchone()
        if row is not None:
            return {
                "path": row[0],
                "inode": row[1],
                "device": row[2],
                "updated_at": row[3],
                "vpath": row[4] if len(row) > 4 else None,
            }
        # Fallback: DB may have stored resolved path (e.g. /private/Users/... on macOS)
        try:
            vpath_resolved = str(Path(vpath).resolve())
            if vpath_resolved == vpath_str:
                return None
            cur = conn.execute(
                "SELECT path, inode, device, updated_at, vpath FROM meta WHERE vpath = ?",
                (vpath_resolved,),
            )
            row = cur.fetchone()
            if row is not None:
                return {
                    "path": row[0],
                    "inode": row[1],
                    "device": row[2],
                    "updated_at": row[3],
                    "vpath": row[4] if len(row) > 4 else None,
                }
        except OSError:
            pass
        return None
    finally:
        conn.close()


def get_path_meta(db_path: Path, path: str | Path) -> Optional[dict]:
    """Return meta row for path if it exists: { path, inode, device, updated_at, vpath }. Else None."""
    path_str = _path_key(path)
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            "SELECT path, inode, device, updated_at, vpath FROM meta WHERE path = ?",
            (path_str,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "path": row[0],
            "inode": row[1],
            "device": row[2],
            "updated_at": row[3],
            "vpath": row[4] if len(row) > 4 else None,
        }
    finally:
        conn.close()


def get_all_meta_for_debug(db_path: Path) -> list[dict]:
    """Return all meta rows with path, vpath, inode (for debugging). Each dict: path, vpath, inode."""
    if not db_path or not Path(db_path).exists():
        return []
    conn = _conn(Path(db_path))
    try:
        cur = conn.execute("SELECT path, vpath, inode FROM meta")
        return [
            {"path": row[0], "vpath": row[1], "inode": row[2]}
            for row in cur.fetchall()
        ]
    finally:
        conn.close()


def _under_scope(full_path: str | None, scope: str | None) -> bool:
    """True if full_path is scope itself or a descendant (path or vpath under that scope)."""
    if not full_path:
        return False
    if not scope or not str(scope).strip():
        return True
    scope_norm = str(_scope_key(scope))
    full = str(full_path).strip()
    # Root "/": any absolute path is under it
    if scope_norm == "/":
        return full == "/" or (full.startswith("/") and len(full) > 1)
    return full == scope_norm or full.startswith(scope_norm + "/")


def get_moved_in_scopes(
    db_path: Path,
    scope_left: str | Path | None,
    scope_right: str | Path | None,
) -> list[dict]:
    """Return meta rows with non-null vpath where path or vpath is under scope_left or scope_right.
    Each dict: path, vpath. Used for CHANGES pane (union of both folder scopes)."""
    if not db_path or not Path(db_path).exists():
        return []
    conn = _conn(Path(db_path))
    try:
        cur = conn.execute("SELECT path, vpath FROM meta WHERE vpath IS NOT NULL")
        rows = [{"path": row[0], "vpath": row[1]} for row in cur.fetchall() if row[1]]
    finally:
        conn.close()
    result = []
    for r in rows:
        path, vpath = r["path"], r["vpath"]
        if _under_scope(path, scope_left) or _under_scope(path, scope_right):
            result.append(r)
            continue
        if _under_scope(vpath, scope_left) or _under_scope(vpath, scope_right):
            result.append(r)
    return result


def path_matches_meta(db_path: Path, path: str | Path) -> bool:
    """
    True if the path has a meta row and the current filesystem inode/device match what we stored.
    Used to detect moves/deletes (stale meta) or confirm the path is unchanged.
    """
    meta = get_path_meta(db_path, path)
    if meta is None:
        return False
    inode, device = _path_stat(Path(path))
    if inode is None:
        return False  # path no longer exists
    return meta["inode"] == inode and meta["device"] == device


def get_tags_from_rules(db_path: Path, path: str) -> list[str]:
    """
    Return list of tags that apply to the given file/folder by matching all
    name_rule_tags patterns against the full path (not just basename).
    Invalid regexes are skipped.
    """
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            "SELECT pattern, tag FROM name_rule_tags ORDER BY pattern, tag"
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    result = []
    seen = set()
    for pattern_str, tag in rows:
        if tag in seen:
            continue
        try:
            if re.search(pattern_str, path, re.IGNORECASE) is not None:
                result.append(tag)
                seen.add(tag)
        except re.error:
            continue
    return result


def get_ancestor_tags(db_path: Path, path: str | Path) -> list[str]:
    """
    Return tags from the path's parent and all ancestors (grandparent, etc.).
    Used for soft-tag inheritance: children inherit tags from parent and above.
    """
    p = Path(path).resolve()
    parent = p.parent
    seen = set()
    result = []
    while parent != p:
        for tag in get_tags(db_path, str(parent)):
            if tag not in seen:
                seen.add(tag)
                result.append(tag)
        p = parent
        parent = p.parent
    return result


def get_all_rules(db_path: Path) -> list[dict]:
    """
    Return all name rules as list of { "pattern": str, "tags": [str] },
    one entry per distinct pattern, tags sorted.
    """
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            "SELECT pattern, tag FROM name_rule_tags ORDER BY pattern, tag"
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    by_pattern = {}
    for pattern, tag in rows:
        if pattern not in by_pattern:
            by_pattern[pattern] = []
        by_pattern[pattern].append(tag)
    return [{"pattern": p, "tags": tags} for p, tags in sorted(by_pattern.items())]


def add_rule_tag(db_path: Path, pattern: str, tag: str) -> None:
    """Add a (pattern, tag) rule. Pattern is applied to full path (vpath or path)."""
    pattern = pattern.strip()
    tag = tag.strip()
    if not pattern or not tag:
        return
    conn = _conn(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO name_rule_tags (pattern, tag) VALUES (?, ?)",
            (pattern, tag),
        )
        conn.commit()
    finally:
        conn.close()


def remove_rule_tag(db_path: Path, pattern: str, tag: str) -> None:
    """Remove one (pattern, tag) rule entry."""
    pattern = pattern.strip()
    tag = tag.strip()
    conn = _conn(db_path)
    try:
        conn.execute(
            "DELETE FROM name_rule_tags WHERE pattern = ? AND tag = ?",
            (pattern, tag),
        )
        conn.commit()
    finally:
        conn.close()


def remove_rule_pattern(db_path: Path, pattern: str) -> None:
    """Remove all rule entries for the given pattern."""
    pattern = pattern.strip()
    if not pattern:
        return
    conn = _conn(db_path)
    try:
        conn.execute("DELETE FROM name_rule_tags WHERE pattern = ?", (pattern,))
        conn.commit()
    finally:
        conn.close()


def update_rule_pattern(db_path: Path, old_pattern: str, new_pattern: str) -> None:
    """Change all rule entries with old_pattern to use new_pattern."""
    old_pattern = old_pattern.strip()
    new_pattern = new_pattern.strip()
    if not old_pattern or not new_pattern or old_pattern == new_pattern:
        return
    conn = _conn(db_path)
    try:
        conn.execute(
            "UPDATE name_rule_tags SET pattern = ? WHERE pattern = ?",
            (new_pattern, old_pattern),
        )
        conn.commit()
    finally:
        conn.close()
