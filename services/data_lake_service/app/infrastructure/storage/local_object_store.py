"""
Object store local (filesystem) para desarrollo y tests.
"""
from __future__ import annotations

from pathlib import Path


class LocalObjectStore:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, data: bytes, content_type: str = "application/json") -> str:
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"file://{path}"

    def get(self, key: str) -> bytes:
        return (self._root / key).read_bytes()
