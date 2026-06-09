"""Lightweight file storage for claim attachments.

Trimmed adaptation of the parent project's utils/file_storage.py — separates
"images" (car-damage photos) from "documents" (bills / police reports / etc.)
so the orchestrator can route each to the right Azure CV agent.
"""

from datetime import datetime
from pathlib import Path
from typing import List


class FileStorage:
    def __init__(self, base_dir: str = "uploads"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _claim_subdir(self, claim_id: str, kind: str) -> Path:
        d = self.base_dir / claim_id / kind
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save(self, claim_id: str, kind: str, content: bytes, filename: str) -> str:
        """Save a file under uploads/{claim_id}/{kind}/. Returns the saved filename."""
        safe = self._sanitize(filename)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = f"{ts}_{safe}"
        path = self._claim_subdir(claim_id, kind) / new_name
        path.write_bytes(content)
        return new_name

    def list_files(self, claim_id: str, kind: str) -> List[Path]:
        d = self._claim_subdir(claim_id, kind)
        return sorted([p for p in d.iterdir() if p.is_file()])

    def get_path(self, claim_id: str, kind: str, filename: str) -> Path:
        return self._claim_subdir(claim_id, kind) / filename

    @staticmethod
    def _sanitize(filename: str) -> str:
        name = Path(filename).name
        for ch in '<>:"/\\|?*':
            name = name.replace(ch, "_")
        return name[:200]


file_storage = FileStorage()
