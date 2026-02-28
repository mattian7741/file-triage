"""
Semantic triage: scan folder tree and emit a Graphviz .dot of folder names and parent-child edges.

Nodes are foldernames (with aliases collapsed to one node). Edges connect parent→child with
the child's folderpath as the edge label. Respects folder.ignore (leaf nodes, no recurse)
and folder.alias (equivalent names).
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Iterator

from .config import load_folder_ignore, load_folder_alias, should_ignore, should_hide


@dataclass
class FolderEntry:
    """A single folder in the tree (path and names)."""

    folderpath: Path  # full path including foldername
    foldername: str   # leaf name
    parentpath: Path  # full path of parent (may be root)
    parentname: str   # parent's leaf name (empty if parent is scan root)


def _walk_folders(
    root: Path,
    exact_ignore: set[str],
    ignore_patterns: list[str],
    *,
    parentpath: Path | None = None,
    parentname: str = "",
) -> Iterator[FolderEntry]:
    root = root.resolve()
    if not root.is_dir():
        return
    try:
        entries = list(os.scandir(root))
    except OSError:
        return

    for entry in entries:
        try:
            if not entry.is_dir(follow_symlinks=False):
                continue
            path = Path(entry.path)
            name = entry.name
            # Emit this folder
            yield FolderEntry(
                folderpath=path,
                foldername=name,
                parentpath=parentpath if parentpath is not None else path.parent,
                parentname=parentname if parentpath is not None else (path.parent.name if path.parent != path else ""),
            )
            # Recurse unless ignored (exact + glob, case-insensitive)
            if not should_ignore(name, exact_ignore, ignore_patterns):
                yield from _walk_folders(
                    path,
                    exact_ignore,
                    ignore_patterns,
                    parentpath=path,
                    parentname=name,
                )
        except OSError:
            continue


def walk_folders(root: Path, exact_ignore: set[str], ignore_patterns: list[str]) -> Iterator[FolderEntry]:
    """Walk directory tree yielding each folder; do not descend into folders in ignore."""
    root = root.resolve()
    # Root itself: treat as a folder with no parent (we still need a node for it)
    yield FolderEntry(
        folderpath=root,
        foldername=root.name or str(root),
        parentpath=root.parent,
        parentname=root.parent.name if root.parent != root else "",
    )
    yield from _walk_folders(root, exact_ignore, ignore_patterns, parentpath=root, parentname=root.name or str(root))


def _canonical(
    name: str,
    name_to_primary: dict[str, str],
    alias_patterns: list[tuple[str, str]],
) -> str:
    """Resolve foldername to canonical: exact match first, then glob patterns. Case-insensitive."""
    key = name.lower()
    if key in name_to_primary:
        return name_to_primary[key]
    for pattern, canon in alias_patterns:
        if fnmatch.fnmatch(key, pattern):
            return canon
    return key


def _node_label(primary: str, primary_to_group: dict[str, list[str]]) -> str:
    """Label for node: primary or 'primary\\nalias1\\nalias2' (newline-separated)."""
    group = primary_to_group.get(primary)
    if group and len(group) > 1:
        return "\n".join(group)
    return primary


def _dot_id(name: str) -> str:
    """Safe Graphviz node ID: use quoted string so different names stay distinct."""
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_graph(
    entries: Iterator[FolderEntry],
    name_to_primary: dict[str, str],
    primary_to_group: dict[str, list[str]],
    alias_patterns: list[tuple[str, str]],
    exact_hide: set[str],
    hide_patterns: list[str],
) -> tuple[dict[str, str], list[tuple[str, str, str]]]:
    """
    Build node labels and edges from folder entries and alias maps.

    Only adds an edge when the parent folder was seen in the scan (so we don't
    link from outside the scanned tree). Folders in folder.hide are omitted from
    the graph only when they are logical leaves (no children on disk, or in folder.ignore).
    """
    nodes: dict[str, str] = {}
    edges: list[tuple[str, str, str]] = []
    seen_paths: set[Path] = set()
    list_entries: list[FolderEntry] = []

    for e in entries:
        list_entries.append(e)
        seen_paths.add(e.folderpath)

    # Logical leaves: folderpaths that are not the parent of any other entry
    parent_paths = {
        e.parentpath
        for e in list_entries
        if e.parentpath != e.folderpath and e.parentpath in seen_paths
    }
    leaf_paths = seen_paths - parent_paths

    def canon(n: str) -> str:
        return _canonical(n, name_to_primary, alias_patterns)

    def is_hidden_leaf(path: Path, name: str) -> bool:
        return path in leaf_paths and should_hide(name, exact_hide, hide_patterns)

    for e in list_entries:
        # Omit entry if child or parent is a hidden logical leaf (don't add node/edge for it)
        if is_hidden_leaf(e.folderpath, e.foldername) or is_hidden_leaf(e.parentpath, e.parentname):
            continue
        parent_canon = canon(e.parentname) if e.parentname else canon(e.foldername)
        child_canon = canon(e.foldername)
        nodes[child_canon] = _node_label(child_canon, primary_to_group)
        if e.parentpath in seen_paths and e.parentpath != e.folderpath:
            nodes[parent_canon] = _node_label(parent_canon, primary_to_group)
            folderpath_str = str(e.folderpath)
            edges.append((parent_canon, child_canon, folderpath_str))

    return nodes, edges


def write_dot(
    nodes: dict[str, str],
    edges: list[tuple[str, str, str]],
    out_path: Path,
) -> None:
    """Write a Graphviz .dot file. Multiple edges (parent, child) are merged with labels combined."""
    # Group edges by (parent, child) to combine labels
    edge_labels: dict[tuple[str, str], list[str]] = {}
    for p, c, label in edges:
        edge_labels.setdefault((p, c), []).append(label)

    lines = ["digraph semantic_triage {", '    rankdir="LR";', '    node [shape="rectangle";]']

    for canon, label in sorted(nodes.items()):
        nid = _dot_id(canon)
        # Escape quotes in label
        label_esc = label.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'    {nid} [label="{label_esc}"]')

    for (p, c), labels in sorted(edge_labels.items()):
        pid, cid = _dot_id(p), _dot_id(c)
        escaped_labels = [l.replace("\\", "\\\\").replace('"', '\\"') for l in labels]
        combined = "\\n".join(escaped_labels)
        lines.append(f'    {pid} -> {cid} [label="{combined}"]')

    lines.append("}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
