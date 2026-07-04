"""
Tests for file access restrictions.
"""

import pytest

from just_prompt.atoms.shared.file_access import resolve_checked_path


def test_default_file_root_is_current_working_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("JUST_PROMPT_FILE_ROOT", raising=False)
    monkeypatch.delenv("FILE_ACCESS_BASE_DIR", raising=False)
    monkeypatch.chdir(tmp_path)

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("hello", encoding="utf-8")
    assert resolve_checked_path(str(prompt_file), must_exist=True) == prompt_file.resolve()

    outside_file = tmp_path.parent / "outside-prompt.txt"
    outside_file.write_text("outside", encoding="utf-8")
    with pytest.raises(ValueError, match="outside the configured file access root"):
        resolve_checked_path(str(outside_file), must_exist=True)


def test_configured_file_root_allows_explicit_workspace(monkeypatch, tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setenv("JUST_PROMPT_FILE_ROOT", str(root))

    prompt_file = root / "prompt.txt"
    prompt_file.write_text("hello", encoding="utf-8")
    assert resolve_checked_path(str(prompt_file), must_exist=True) == prompt_file.resolve()

    outside_file = tmp_path / "outside-prompt.txt"
    outside_file.write_text("outside", encoding="utf-8")
    with pytest.raises(ValueError, match="outside the configured file access root"):
        resolve_checked_path(str(outside_file), must_exist=True)


def test_missing_file_error_explains_resolution_and_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("JUST_PROMPT_FILE_ROOT", raising=False)
    monkeypatch.delenv("FILE_ACCESS_BASE_DIR", raising=False)

    with pytest.raises(FileNotFoundError) as exc_info:
        resolve_checked_path("missing-prompt.txt", must_exist=True)

    message = str(exc_info.value)
    assert "File not found: missing-prompt.txt" in message
    assert "Resolved path:" in message
    assert f"Configured file access root: {tmp_path.resolve()}" in message
    assert "resolved it against server cwd" in message
    assert "JUST_PROMPT_FILE_ROOT" in message


def test_outside_root_error_explains_how_to_fix(monkeypatch, tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    outside_file = tmp_path / "outside-prompt.txt"
    outside_file.write_text("outside", encoding="utf-8")
    monkeypatch.setenv("JUST_PROMPT_FILE_ROOT", str(root))

    with pytest.raises(ValueError) as exc_info:
        resolve_checked_path(str(outside_file), must_exist=True)

    message = str(exc_info.value)
    assert "Path is outside the configured file access root" in message
    assert f"Resolved path: {outside_file.resolve()}" in message
    assert f"Configured root: {root.resolve()}" in message
    assert "--file-access-root" in message
