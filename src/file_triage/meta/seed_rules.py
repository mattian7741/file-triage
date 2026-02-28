"""
Default name-pattern rules for the meta overlay.

Tag strategy: macro, mid, micro (e.g. media, image, jpg).
Patterns match against full path (vpath or path), case-insensitive.
"""

from __future__ import annotations

from pathlib import Path

from .db import init_db, _conn

# (pattern, tag) — pattern is regex on full path; tag is one of macro/mid/micro
# Extensions are matched with .*\.ext$ so "file.EXT" matches.
def _ext_pattern(ext: str) -> str:
    return r".*\." + ext + r"$"


# List of (pattern, tag) to add. Order: macro, mid, micro per type.
DEFAULT_NAME_RULES: list[tuple[str, str]] = []


def _add(ext: str, macro: str, mid: str, micro: str | None = None) -> None:
    p = _ext_pattern(ext)
    DEFAULT_NAME_RULES.append((p, macro))
    DEFAULT_NAME_RULES.append((p, mid))
    if micro is not None:
        DEFAULT_NAME_RULES.append((p, micro))
    else:
        DEFAULT_NAME_RULES.append((p, ext))


# --- Media > Image ---
_add("jpg", "media", "image", "jpg")
_add("jpeg", "media", "image", "jpeg")
_add("png", "media", "image", "png")
_add("gif", "media", "image", "gif")
_add("bmp", "media", "image", "bmp")
_add("tga", "media", "image", "tga")
_add("psd", "media", "image", "psd")
_add("webp", "media", "image", "webp")
_add("svg", "media", "image", "svg")
_add("ico", "media", "image", "ico")
_add("heic", "media", "image", "heic")
_add("tiff", "media", "image", "tiff")
_add("tif", "media", "image", "tif")

# --- Media > Audio ---
_add("wav", "media", "audio", "wav")
_add("mp3", "media", "audio", "mp3")
_add("m4a", "media", "audio", "m4a")
_add("flac", "media", "audio", "flac")
_add("ogg", "media", "audio", "ogg")
_add("aac", "media", "audio", "aac")
_add("wma", "media", "audio", "wma")
_add("aiff", "media", "audio", "aiff")
_add("aif", "media", "audio", "aif")

# --- Media > Video ---
_add("mp4", "media", "video", "mp4")
_add("mov", "media", "video", "mov")
_add("avi", "media", "video", "avi")
_add("mkv", "media", "video", "mkv")
_add("wmv", "media", "video", "wmv")
_add("webm", "media", "video", "webm")
_add("m4v", "media", "video", "m4v")
_add("flv", "media", "video", "flv")
_add("mpeg", "media", "video", "mpeg")
_add("mpg", "media", "video", "mpg")

# --- Document ---
_add("pdf", "document", "pdf", "pdf")
_add("doc", "document", "doc", "doc")
_add("docx", "document", "doc", "docx")
_add("txt", "document", "text", "txt")
_add("md", "document", "markdown", "md")
_add("markdown", "document", "markdown", "markdown")
_add("rtf", "document", "rtf", "rtf")
_add("xls", "document", "spreadsheet", "xls")
_add("xlsx", "document", "spreadsheet", "xlsx")
_add("xml", "document", "xml", "xml")
_add("json", "document", "json", "json")
_add("csv", "document", "data", "csv")
_add("yaml", "document", "data", "yaml")
_add("yml", "document", "data", "yml")
_add("ppt", "document", "presentation", "ppt")
_add("pptx", "document", "presentation", "pptx")
_add("odt", "document", "doc", "odt")
_add("ods", "document", "spreadsheet", "ods")

# --- Archive / container ---
_add("zip", "archive", "zip", "zip")
_add("jar", "archive", "jar", "jar")
_add("dmg", "archive", "dmg", "dmg")
_add("tar", "archive", "tar", "tar")
_add("gz", "archive", "gz", "gz")
_add("tgz", "archive", "tar", "tgz")
_add("rar", "archive", "rar", "rar")
_add("7z", "archive", "7z", "7z")

# --- Code / development ---
_add("cpp", "code", "cpp", "cpp")
_add("cxx", "code", "cpp", "cxx")
_add("cc", "code", "cpp", "cc")
_add("h", "code", "cpp", "h")
_add("hpp", "code", "cpp", "hpp")
_add("js", "code", "javascript", "js")
_add("mjs", "code", "javascript", "mjs")
_add("cjs", "code", "javascript", "cjs")
_add("ts", "code", "typescript", "ts")
_add("tsx", "code", "typescript", "tsx")
_add("css", "code", "css", "css")
_add("scss", "code", "css", "scss")
_add("html", "code", "html", "html")
_add("htm", "code", "html", "htm")
_add("bat", "code", "batch", "bat")
_add("cmd", "code", "batch", "cmd")
_add("java", "code", "java", "java")
_add("class", "code", "java", "class")
_add("php", "code", "php", "php")
_add("jsp", "code", "jsp", "jsp")
_add("py", "code", "python", "py")
_add("pyc", "code", "python", "pyc")
_add("asp", "code", "asp", "asp")
_add("aspx", "code", "asp", "aspx")
_add("sh", "code", "shell", "sh")
_add("bash", "code", "shell", "bash")
_add("zsh", "code", "shell", "zsh")
_add("rb", "code", "ruby", "rb")
_add("swift", "code", "swift", "swift")
_add("go", "code", "go", "go")
_add("rs", "code", "rust", "rs")
_add("sql", "code", "sql", "sql")
_add("vue", "code", "vue", "vue")
_add("svelte", "code", "svelte", "svelte")

# --- Design / 3D ---
_add("skp", "design", "sketchup", "skp")
_add("blend", "design", "blender", "blend")
_add("max", "design", "3dsmax", "max")
_add("dwg", "design", "cad", "dwg")
_add("dxf", "design", "cad", "dxf")

# --- System / executable / config ---
_add("exe", "system", "executable", "exe")
_add("ini", "system", "config", "ini")
_add("url", "system", "url", "url")
_add("bak", "system", "backup", "bak")
_add("log", "system", "log", "log")
_add("cfg", "system", "config", "cfg")
_add("conf", "system", "config", "conf")
_add("dll", "system", "executable", "dll")
_add("so", "system", "executable", "so")
_add("dylib", "system", "executable", "dylib")


def seed_default_rules(db_path: Path) -> int:
    """Ensure default name-pattern rules exist. Uses INSERT OR IGNORE so existing rules are kept. Returns count of (pattern, tag) pairs added."""
    init_db(db_path)
    conn = _conn(db_path)
    added = 0
    try:
        for pattern, tag in DEFAULT_NAME_RULES:
            cur = conn.execute(
                "INSERT OR IGNORE INTO name_rule_tags (pattern, tag) VALUES (?, ?)",
                (pattern, tag),
            )
            if cur.rowcount:
                added += 1
        conn.commit()
    finally:
        conn.close()
    return added
