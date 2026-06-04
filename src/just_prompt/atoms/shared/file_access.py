"""
Optional file access restrictions for file-based MCP tools.
"""

import os
from pathlib import Path


def configured_file_root() -> Path:
    """
    Return the file-access root.

    The default is the server's current working directory so file-based MCP
    tools never expose the entire local filesystem when no explicit root is set.
    """
    value = os.environ.get("JUST_PROMPT_FILE_ROOT") or os.environ.get("FILE_ACCESS_BASE_DIR")
    if not value or not value.strip():
        return Path.cwd().resolve()
    return Path(value).expanduser().resolve()


def resolve_checked_path(path: str, *, must_exist: bool = False) -> Path:
    """
    Resolve a path and ensure it stays inside the optional configured root.
    """
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate

    resolved = candidate.resolve(strict=must_exist)
    root = configured_file_root()

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path is outside the configured file access root: {path}") from exc

    return resolved
