from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException


def safe_path_join(base_dir: str, relative_path: str) -> Path:
    base = Path(base_dir).resolve()
    target = (base / relative_path).resolve()
    if base not in target.parents and target != base:
        raise HTTPException(status_code=400, detail="Invalid file path")
    return target


def sanitize_filename_component(value: str) -> str:
    keep = []
    for ch in value:
        if ch.isalnum() or ch in {"-", "_", "."}:
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep).strip("._") or "file"
