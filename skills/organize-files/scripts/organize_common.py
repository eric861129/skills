#!/usr/bin/env python3
"""Shared helpers for the organize-files scripts (standard library only).

Nothing in this module deletes files. The scripts move files, move files into
a staging folder, create folders, and (only when a manifest explicitly allows
it) remove folders that are already empty.
"""

from __future__ import annotations

from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Iterable

SCHEMA_VERSION = "1.0"
STAGING_DIR_NAME = "_organize-staging"
LOG_DIR_NAME = "organize-files-logs"
IS_WINDOWS = os.name == "nt"

EXCLUDED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "$RECYCLE.BIN",
    "System Volume Information",
    ".Trash",
    ".Trashes",
    ".Spotlight-V100",
    ".fseventsd",
    ".DocumentRevisions-V100",
    STAGING_DIR_NAME,
}

# A directory containing one of these entries is an atomic unit: it is moved
# as a whole or not at all, because its contents depend on relative paths.
UNIT_MARKER_FILES = {
    ".git": "git-repo",
    ".hg": "hg-repo",
    ".svn": "svn-checkout",
    "package.json": "project",
    "pyproject.toml": "project",
    "setup.py": "project",
    "Cargo.toml": "project",
    "go.mod": "project",
    "pom.xml": "project",
    "build.gradle": "project",
    "CMakeLists.txt": "project",
    "project.godot": "project",
    "ProjectSettings": "project",
}
UNIT_MARKER_SUFFIXES = {
    ".sln": "project",
    ".csproj": "project",
    ".uproject": "project",
    ".lrcat": "lightroom-catalog",
    ".vmx": "virtual-machine",
    ".vbox": "virtual-machine",
    ".vmcx": "virtual-machine",
}
UNIT_DIR_SUFFIXES = {
    ".app": "app-bundle",
    ".photoslibrary": "photos-library",
    ".lrdata": "lightroom-catalog",
    ".fcpbundle": "video-library",
    ".bundle": "bundle",
    ".pvm": "virtual-machine",
}

CATEGORIES: dict[str, set[str]] = {
    "image": {
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp",
        ".heic", ".heif", ".raw", ".cr2", ".cr3", ".nef", ".arw", ".dng",
        ".orf", ".rw2", ".svg", ".ico", ".psd",
    },
    "video": {
        ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v",
        ".mts", ".m2ts", ".3gp",
    },
    "audio": {
        ".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma", ".opus",
        ".aiff", ".mid", ".midi",
    },
    "document": {".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".pages", ".tex"},
    "spreadsheet": {".xls", ".xlsx", ".xlsm", ".csv", ".tsv", ".ods", ".numbers"},
    "presentation": {".ppt", ".pptx", ".odp", ".key"},
    "ebook": {".epub", ".mobi", ".azw", ".azw3"},
    "archive": {
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".zst",
        ".iso", ".img", ".dmg",
    },
    "installer": {".exe", ".msi", ".msix", ".appx", ".pkg", ".deb", ".rpm", ".apk", ".appimage"},
    "code": {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".h", ".cpp",
        ".hpp", ".cs", ".go", ".rs", ".rb", ".php", ".html", ".css", ".scss",
        ".json", ".yaml", ".yml", ".toml", ".xml", ".sh", ".ps1", ".bat",
        ".sql", ".ipynb", ".lua", ".gd", ".kt", ".swift",
    },
    "font": {".ttf", ".otf", ".woff", ".woff2"},
    "design": {".ai", ".fig", ".sketch", ".xd", ".indd", ".blend", ".fbx", ".obj"},
    "shortcut": {".lnk", ".url", ".webloc", ".desktop"},
    "partial-download": {".crdownload", ".part", ".partial", ".download", ".tmp"},
}
_EXT_TO_CATEGORY = {ext: cat for cat, exts in CATEGORIES.items() for ext in exts}

# Windows file attribute bits.
FILE_ATTRIBUTE_READONLY = 0x1
FILE_ATTRIBUTE_HIDDEN = 0x2
FILE_ATTRIBUTE_SYSTEM = 0x4
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
FILE_ATTRIBUTE_OFFLINE = 0x1000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x40000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000

WINDOWS_PATH_LIMIT = 260


# --------------------------------------------------------------------------
# Small utilities
# --------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def configure_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def human_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{num_bytes} B"


def category_for(path: Path) -> str:
    name = path.name
    if name.startswith("~$") or name.startswith(".~lock."):
        return "office-lock-file"
    return _EXT_TO_CATEGORY.get(path.suffix.lower(), "other")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def norm_key(path: Path | str) -> str:
    """Comparison key for paths (case-insensitive on Windows)."""
    return os.path.normcase(os.path.normpath(str(path)))


def is_within(child: Path, parent: Path) -> bool:
    try:
        common = os.path.commonpath([norm_key(child), norm_key(parent)])
    except ValueError:
        return False
    return common == norm_key(parent)


def rel_posix(path: Path, root: Path) -> str:
    try:
        return Path(os.path.relpath(path, root)).as_posix()
    except ValueError:
        return str(path)


def safe_name(text: str) -> str:
    cleaned = re.sub(r"[^\w.-]+", "-", text, flags=re.UNICODE).strip("-")
    return cleaned or "root"


def new_run_id(root: Path) -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + safe_name(root.name)


# --------------------------------------------------------------------------
# Desktop / log directory
# --------------------------------------------------------------------------

def _windows_desktop() -> Path | None:
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        folderid_desktop = GUID(
            0xB4BFCC3A, 0xDB2C, 0x424C,
            (ctypes.c_ubyte * 8)(0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41),
        )
        path_ptr = ctypes.c_wchar_p()
        shell32 = ctypes.WinDLL("shell32")
        result = shell32.SHGetKnownFolderPath(
            ctypes.byref(folderid_desktop), 0, None, ctypes.byref(path_ptr)
        )
        if result != 0:
            return None
        value = path_ptr.value
        ctypes.WinDLL("ole32").CoTaskMemFree(path_ptr)
        return Path(value) if value else None
    except Exception:
        return None


def _xdg_desktop() -> Path | None:
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "user-dirs.dirs"
    if not config.exists():
        return None
    for line in config.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r'\s*XDG_DESKTOP_DIR="(.+)"', line)
        if match:
            return Path(match.group(1).replace("$HOME", str(Path.home())))
    return None


def desktop_dir() -> Path:
    """The user's Desktop folder (follows OneDrive/known-folder redirection)."""
    candidates = []
    if IS_WINDOWS:
        candidates.append(_windows_desktop())
    else:
        candidates.append(_xdg_desktop())
    candidates.append(Path.home() / "Desktop")
    for candidate in candidates:
        if candidate and candidate.is_dir():
            return candidate
    return Path.home()


def log_base_dir() -> Path:
    override = os.environ.get("ORGANIZE_FILES_LOG_DIR")
    if override:
        return Path(override)
    return desktop_dir() / LOG_DIR_NAME


# --------------------------------------------------------------------------
# Atomic units and file flags
# --------------------------------------------------------------------------

def unit_kind(directory: Path) -> str | None:
    """Return the atomic-unit kind of a directory, or None."""
    lowered = directory.name.lower()
    for suffix, kind in UNIT_DIR_SUFFIXES.items():
        if lowered.endswith(suffix):
            return kind
    try:
        names = os.listdir(directory)
    except OSError:
        return None
    for name in names:
        if name in UNIT_MARKER_FILES:
            return UNIT_MARKER_FILES[name]
        suffix = os.path.splitext(name)[1].lower()
        if suffix in UNIT_MARKER_SUFFIXES:
            return UNIT_MARKER_SUFFIXES[suffix]
    return None


def enclosing_unit(path: Path, root: Path) -> Path | None:
    """The nearest atomic unit strictly containing `path`, below `root`."""
    current = path.parent
    while is_within(current, root) and norm_key(current) != norm_key(root):
        if unit_kind(current):
            return current
        current = current.parent
    return None


def stat_flags(path: Path, st: os.stat_result) -> list[str]:
    flags: list[str] = []
    attributes = getattr(st, "st_file_attributes", 0)
    if attributes:
        if attributes & FILE_ATTRIBUTE_HIDDEN:
            flags.append("hidden")
        if attributes & FILE_ATTRIBUTE_SYSTEM:
            flags.append("system")
        if attributes & FILE_ATTRIBUTE_READONLY:
            flags.append("readonly")
        if attributes & FILE_ATTRIBUTE_REPARSE_POINT:
            flags.append("reparse-point")
        if attributes & (
            FILE_ATTRIBUTE_OFFLINE
            | FILE_ATTRIBUTE_RECALL_ON_OPEN
            | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
        ):
            flags.append("cloud-placeholder")
    elif path.name.startswith("."):
        flags.append("hidden")
    if path.is_symlink():
        flags.append("symlink")
    if len(str(path)) >= WINDOWS_PATH_LIMIT:
        flags.append("long-path")
    return flags


def is_cloud_placeholder(path: Path) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return "cloud-placeholder" in stat_flags(path, st)


# --------------------------------------------------------------------------
# Lock detection
# --------------------------------------------------------------------------

def windows_rename_blocked(path: Path) -> str | None:
    """Return 'locked' / 'permission_denied' if Windows would refuse to move it.

    Opens the path with DELETE access while sharing everything, which is the
    access a rename needs. Another process holding the file without
    FILE_SHARE_DELETE makes this fail with a sharing violation.
    """
    if not IS_WINDOWS:
        return None
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    delete_access = 0x00010000
    share_all = 0x1 | 0x2 | 0x4
    open_existing = 3
    backup_semantics = 0x02000000  # required to open directories
    open_reparse_point = 0x00200000
    handle = create_file(
        str(path), delete_access, share_all, None, open_existing,
        backup_semantics | open_reparse_point, None,
    )
    invalid = ctypes.c_void_p(-1).value
    if handle in (invalid, None):
        error = ctypes.get_last_error()
        if error in (32, 33):
            return "locked"
        if error == 5:
            return "permission_denied"
        return None
    kernel32.CloseHandle(handle)
    return None


def lock_holders(path: Path) -> list[str]:
    """Best-effort list of processes holding `path` open ("name (pid N)")."""
    try:
        if IS_WINDOWS:
            return _restart_manager_holders(path)
        return _lsof_holders(path)
    except Exception:
        return []


def _restart_manager_holders(path: Path) -> list[str]:
    import ctypes
    from ctypes import wintypes

    class RM_UNIQUE_PROCESS(ctypes.Structure):
        _fields_ = [("dwProcessId", wintypes.DWORD), ("ProcessStartTime", wintypes.FILETIME)]

    class RM_PROCESS_INFO(ctypes.Structure):
        _fields_ = [
            ("Process", RM_UNIQUE_PROCESS),
            ("strAppName", wintypes.WCHAR * 256),
            ("strServiceShortName", wintypes.WCHAR * 64),
            ("ApplicationType", ctypes.c_int),
            ("AppStatus", wintypes.ULONG),
            ("TSSessionId", wintypes.DWORD),
            ("bRestartable", wintypes.BOOL),
        ]

    rm = ctypes.WinDLL("rstrtmgr")
    session = wintypes.DWORD()
    key = ctypes.create_unicode_buffer(33)
    if rm.RmStartSession(ctypes.byref(session), 0, key) != 0:
        return []
    try:
        files = (ctypes.c_wchar_p * 1)(str(path))
        if rm.RmRegisterResources(session, 1, files, 0, None, 0, None) != 0:
            return []
        needed = wintypes.UINT(0)
        count = wintypes.UINT(0)
        reasons = wintypes.DWORD()
        result = rm.RmGetList(session, ctypes.byref(needed), ctypes.byref(count), None, ctypes.byref(reasons))
        if result == 0:
            return []
        if result != 234:  # ERROR_MORE_DATA
            return []
        infos = (RM_PROCESS_INFO * needed.value)()
        count = wintypes.UINT(needed.value)
        result = rm.RmGetList(session, ctypes.byref(needed), ctypes.byref(count), infos, ctypes.byref(reasons))
        if result != 0:
            return []
        return [
            f"{infos[i].strAppName} (pid {infos[i].Process.dwProcessId})"
            for i in range(count.value)
        ]
    finally:
        rm.RmEndSession(session)


def _lsof_holders(path: Path) -> list[str]:
    if not shutil.which("lsof"):
        return []
    completed = subprocess.run(
        ["lsof", "-F", "pc", "--", str(path)],
        capture_output=True, text=True, timeout=10, check=False,
    )
    holders, pid = [], None
    for line in completed.stdout.splitlines():
        if line.startswith("p"):
            pid = line[1:]
        elif line.startswith("c") and pid:
            holders.append(f"{line[1:]} (pid {pid})")
    return holders


# --------------------------------------------------------------------------
# Error classification
# --------------------------------------------------------------------------

class OrganizeError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


def classify_os_error(error: OSError) -> str:
    winerror = getattr(error, "winerror", None)
    if winerror in (32, 33):
        return "locked"
    if winerror == 17 or error.errno == errno.EXDEV:
        return "cross_volume"
    if winerror == 3 and len(str(getattr(error, "filename2", "") or getattr(error, "filename", "") or "")) >= WINDOWS_PATH_LIMIT:
        return "path_too_long"
    if winerror == 206 or error.errno == errno.ENAMETOOLONG:
        return "path_too_long"
    if winerror in (39, 112) or error.errno == errno.ENOSPC:
        return "disk_full"
    if winerror in (80, 183) or error.errno == errno.EEXIST:
        return "target_exists"
    if winerror in (2, 3) or error.errno == errno.ENOENT:
        return "source_missing"
    if winerror == 5 or error.errno in (errno.EACCES, errno.EPERM):
        return "permission_denied"
    return "failed"


# --------------------------------------------------------------------------
# Tree rendering
# --------------------------------------------------------------------------

def scan_tree(root: Path, excluded: Iterable[str] = EXCLUDED_DIR_NAMES) -> dict[str, Any]:
    """Build a nested summary of `root`; atomic units are not descended."""
    excluded = set(excluded)

    def walk(directory: Path) -> dict[str, Any]:
        node: dict[str, Any] = {
            "name": directory.name or str(directory),
            "files": 0, "bytes": 0, "dirs": [], "file_entries": [], "unit": None,
        }
        try:
            entries = sorted(os.scandir(directory), key=lambda e: e.name.lower())
        except OSError:
            node["unreadable"] = True
            return node
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name in excluded:
                        continue
                    child_path = Path(entry.path)
                    kind = unit_kind(child_path)
                    if kind:
                        files, size = count_tree(child_path)
                        node["dirs"].append({
                            "name": entry.name, "files": files, "bytes": size,
                            "dirs": [], "file_entries": [], "unit": kind,
                        })
                        node["files"] += files
                        node["bytes"] += size
                        continue
                    child = walk(child_path)
                    node["dirs"].append(child)
                    node["files"] += child["files"]
                    node["bytes"] += child["bytes"]
                else:
                    size = entry.stat(follow_symlinks=False).st_size
                    node["file_entries"].append((entry.name, size))
                    node["files"] += 1
                    node["bytes"] += size
            except OSError:
                continue
        return node

    return walk(root)


def count_tree(directory: Path) -> tuple[int, int]:
    files = size = 0
    for current, _dirs, names in os.walk(directory):
        for name in names:
            try:
                size += os.lstat(os.path.join(current, name)).st_size
                files += 1
            except OSError:
                continue
    return files, size


def render_tree(node: dict[str, Any], depth: int = 3, max_files: int = 12) -> str:
    lines = [f"{node['name']}/  ({node['files']} files, {human_size(node['bytes'])})"]

    def render(current: dict[str, Any], prefix: str, level: int) -> None:
        children: list[tuple[str, Any]] = [("dir", d) for d in current["dirs"]]
        files = current["file_entries"]
        if len(files) <= max_files:
            children += [("file", f) for f in files]
        else:
            total = sum(size for _name, size in files)
            children.append(("summary", f"… {len(files)} files ({human_size(total)})"))
        for index, (kind, item) in enumerate(children):
            last = index == len(children) - 1
            branch = "└── " if last else "├── "
            extension = "    " if last else "│   "
            if kind == "dir":
                label = f"{item['name']}/  ({item['files']} files, {human_size(item['bytes'])})"
                if item.get("unit"):
                    label += f"  [unit: {item['unit']}]"
                lines.append(prefix + branch + label)
                if level < depth and not item.get("unit"):
                    render(item, prefix + extension, level + 1)
            elif kind == "file":
                lines.append(prefix + branch + f"{item[0]}  ({human_size(item[1])})")
            else:
                lines.append(prefix + branch + item)

    if depth > 0:
        render(node, "", 1)
    return "\n".join(lines)
