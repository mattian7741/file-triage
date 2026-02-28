"""
CLI for File Triage.

Example: scan one or more directories and print a short summary.
  python -m file_triage scan /path/to/disk1 /path/to/disk2
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from . import __version__
from .scan import scan_roots
from .semantic_triage import (
    walk_folders,
    build_graph,
    write_dot,
)
from .config import load_folder_ignore, load_folder_alias, load_folder_hide


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """File Triage — analyse and organise chaotic file collections across disks."""
    pass


@main.command()
@click.argument("roots", type=click.Path(path_type=Path, exists=True), nargs=-1, required=True)
@click.option("--follow-symlinks", is_flag=True, help="Follow symlinks (default: no)")
@click.option("--count-only", is_flag=True, help="Only print total file/dir counts")
def scan(roots: tuple[Path, ...], follow_symlinks: bool, count_only: bool) -> None:
    """Scan one or more directory roots and list or summarise contents."""
    if not roots:
        click.echo("Please provide at least one root path.", err=True)
        sys.exit(1)

    n_files = 0
    n_dirs = 0
    total_bytes = 0

    try:
        for entry in scan_roots(list(roots), follow_symlinks=follow_symlinks):
            if entry.is_dir:
                n_dirs += 1
            else:
                n_files += 1
                total_bytes += entry.size_bytes
            if not count_only:
                click.echo(entry.path)
    except KeyboardInterrupt:
        click.echo("\nInterrupted.", err=True)
        sys.exit(130)

    if count_only or n_files or n_dirs:
        click.echo("---", err=True)
        click.echo(f"Directories: {n_dirs}, Files: {n_files}, Total size: {total_bytes:,} bytes", err=True)


@main.command("semantic-triage")
@click.argument("root", type=click.Path(path_type=Path, exists=True), required=True)
@click.option(
    "--ignore-file",
    type=click.Path(path_type=Path, exists=True),
    default=None,
    help="Path to folder.ignore (default: folder.ignore in current directory)",
)
@click.option(
    "--alias-file",
    type=click.Path(path_type=Path, exists=True),
    default=None,
    help="Path to folder.alias (default: folder.alias in current directory)",
)
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=Path("semantic-triage.dot"),
    help="Output .dot file (default: semantic-triage.dot in current directory)",
)
def semantic_triage(
    root: Path,
    ignore_file: Path | None,
    alias_file: Path | None,
    output_path: Path,
) -> None:
    """Scan a root and emit a Graphviz .dot of folder names and parent-child edges."""
    cwd = Path.cwd()
    ignore_path = ignore_file or cwd / "folder.ignore"
    alias_path = alias_file or cwd / "folder.alias"
    hide_path = cwd / "folder.hide"

    exact_ignore, ignore_patterns = load_folder_ignore(ignore_path)
    name_to_primary, primary_to_group, alias_patterns = load_folder_alias(alias_path)
    exact_hide, hide_patterns = load_folder_hide(hide_path)

    root = root.resolve()
    entries = walk_folders(root, exact_ignore, ignore_patterns)
    nodes, edges = build_graph(
        entries, name_to_primary, primary_to_group, alias_patterns, exact_hide, hide_patterns
    )
    out = output_path.resolve()
    write_dot(nodes, edges, out)
    click.echo(f"Wrote {out}", err=True)


@main.command()
@click.option(
    "--host",
    default="127.0.0.1",
    help="Bind address (default: 127.0.0.1)",
)
@click.option(
    "--port",
    default=5001,
    type=int,
    help="Port (default: 5001; avoid 5000 on macOS — often used by AirPlay)",
)
@click.option(
    "--meta-db",
    "meta_db_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to meta overlay SQLite DB (default: ~/.file-triage/meta.db); enables tagging in Explorer",
)
def explorer(host: str, port: int, meta_db_path: Path | None) -> None:
    """Start the Explorer web UI (read-only file system browser)."""
    from .explorer.app import create_app
    db_path = meta_db_path or Path.home() / ".file-triage" / "meta.db"
    app = create_app(meta_db_path=db_path)
    click.echo(f"Explorer at http://{host}:{port}/", err=True)
    app.run(host=host, port=port, debug=False, threaded=True)


@main.group()
@click.option(
    "--db",
    "db_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to meta overlay SQLite DB (default: ~/.file-triage/meta.db)",
)
@click.pass_context
def meta(ctx: click.Context, db_path: Path | None) -> None:
    """Meta overlay: tags and metadata for files/folders (SQLite, does not touch the filesystem)."""
    ctx.ensure_object(dict)
    ctx.obj["meta_db"] = db_path or Path.home() / ".file-triage" / "meta.db"


@meta.command("init")
@click.pass_context
def meta_init(ctx: click.Context) -> None:
    """Create or ensure the meta overlay database and schema."""
    from .meta import init_db
    init_db(ctx.obj["meta_db"])
    click.echo(f"Initialized meta DB at {ctx.obj['meta_db']}", err=True)


@meta.command("add-tag")
@click.argument("path", type=click.Path(path_type=Path, exists=True))
@click.argument("tag", type=str)
@click.pass_context
def meta_add_tag(ctx: click.Context, path: Path, tag: str) -> None:
    """Add a tag to a file or folder."""
    from .meta import init_db, add_tag
    db_path = ctx.obj["meta_db"]
    init_db(db_path)
    add_tag(db_path, path, tag)
    click.echo(f"Added tag '{tag}' to {path}")


@meta.command("remove-tag")
@click.argument("path", type=click.Path(path_type=Path, exists=True))
@click.argument("tag", type=str)
@click.pass_context
def meta_remove_tag(ctx: click.Context, path: Path, tag: str) -> None:
    """Remove a tag from a file or folder."""
    from .meta import remove_tag
    remove_tag(ctx.obj["meta_db"], path, tag)
    click.echo(f"Removed tag '{tag}' from {path}")


@meta.command("get-tags")
@click.argument("path", type=click.Path(path_type=Path, exists=True))
@click.pass_context
def meta_get_tags(ctx: click.Context, path: Path) -> None:
    """Print tags for a file or folder."""
    from .meta import get_tags
    for t in get_tags(ctx.obj["meta_db"], path):
        click.echo(t)


@meta.command("seed-default-rules")
@click.pass_context
def meta_seed_default_rules(ctx: click.Context) -> None:
    """Add default name-pattern rules (media/document/code/system etc.) if not already present."""
    from .meta import init_db
    from .meta.seed_rules import seed_default_rules
    db_path = ctx.obj["meta_db"]
    init_db(db_path)
    added = seed_default_rules(db_path)
    click.echo(f"Added {added} default name-pattern rule tags (existing rules were left unchanged).", err=True)


if __name__ == "__main__":
    main()
