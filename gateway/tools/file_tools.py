"""
file_tools.py — scoped file read/write for the agent.

Everything is confined under WORKSPACE_ROOT. No path is allowed to escape it —
this is what stops a model from being tricked (by a prompt injection in a document
it's summarizing, for instance) into reading or writing somewhere it shouldn't.
"""

from __future__ import annotations
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent.parent / "workspace"
WORKSPACE_ROOT.mkdir(exist_ok=True)


class PathEscapeError(Exception):
    pass


def _resolve_safe(relative_path: str) -> Path:
    candidate = (WORKSPACE_ROOT / relative_path).resolve()
    if WORKSPACE_ROOT.resolve() not in candidate.parents and candidate != WORKSPACE_ROOT.resolve():
        raise PathEscapeError(f"Path '{relative_path}' escapes the workspace root — refused.")
    return candidate


def read_file(relative_path: str) -> str:
    path = _resolve_safe(relative_path)
    if not path.exists():
        raise FileNotFoundError(f"{relative_path} not found in workspace")
    return path.read_text(encoding="utf-8", errors="ignore")


def write_file(relative_path: str, content: str) -> Path:
    path = _resolve_safe(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def list_files(subdir: str = ".") -> list[str]:
    base = _resolve_safe(subdir)
    return [str(p.relative_to(WORKSPACE_ROOT)) for p in base.rglob("*") if p.is_file()]


if __name__ == "__main__":
    write_file("notes/demo.txt", "This proves scoped file write works.")
    print("Files in workspace:", list_files())
    print("Read back:", read_file("notes/demo.txt"))
    try:
        read_file("../../../etc/passwd")
    except PathEscapeError as e:
        print("Correctly blocked:", e)
