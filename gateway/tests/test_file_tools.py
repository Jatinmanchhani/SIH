import pytest

from tools import file_tools


def test_write_then_read_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(file_tools, "WORKSPACE_ROOT", tmp_path)
    file_tools.write_file("notes/demo.txt", "hello")
    assert file_tools.read_file("notes/demo.txt") == "hello"
    assert "notes/demo.txt" in file_tools.list_files()


def test_path_escape_is_blocked(monkeypatch, tmp_path):
    monkeypatch.setattr(file_tools, "WORKSPACE_ROOT", tmp_path)
    with pytest.raises(file_tools.PathEscapeError):
        file_tools.read_file("../../../etc/passwd")


def test_missing_file_raises_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(file_tools, "WORKSPACE_ROOT", tmp_path)
    with pytest.raises(FileNotFoundError):
        file_tools.read_file("nope.txt")