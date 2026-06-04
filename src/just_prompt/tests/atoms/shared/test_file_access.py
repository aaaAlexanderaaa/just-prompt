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
