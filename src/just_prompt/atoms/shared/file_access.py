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
    if not path or not str(path).strip():
        raise ValueError(
            "File path is required. Pass an absolute path inside the configured "
            f"file access root: {configured_file_root()}"
        )

    candidate = Path(path).expanduser()
    was_relative = not candidate.is_absolute()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate

    root = configured_file_root()
    if must_exist and not candidate.exists():
        relative_note = (
            f" The path was relative, so just-prompt resolved it against server cwd {Path.cwd()}."
            if was_relative
            else ""
        )
        raise FileNotFoundError(
            f"File not found: {path}. Resolved path: {candidate.resolve(strict=False)}. "
            f"Configured file access root: {root}.{relative_note} "
            "Create the file before calling this tool, pass its absolute path, and ensure it "
            "is inside the configured root. Set JUST_PROMPT_FILE_ROOT or --file-access-root "
            "if the file intentionally lives elsewhere."
        )

    resolved = candidate.resolve(strict=must_exist)

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"Path is outside the configured file access root. Input path: {path}. "
            f"Resolved path: {resolved}. Configured root: {root}. Move/create the file "
            "inside that root, or restart/configure just-prompt with JUST_PROMPT_FILE_ROOT "
            "or --file-access-root pointing at the workspace you want to expose."
        ) from exc

    return resolved
