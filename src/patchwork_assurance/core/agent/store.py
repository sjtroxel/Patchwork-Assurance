"""Flat JSON store for last-seen content hashes (Phase 9 Batch 1).

Intentionally simple: a handful of sources don't need a database. The file is
written only when the caller explicitly calls save(), so a failed pipeline run
doesn't permanently advance the cursor past unprocessed changes.
"""

from __future__ import annotations

import json
from pathlib import Path


class HashStore:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._data: dict[str, str] = {}
        if self._path.exists():
            self._data = json.loads(self._path.read_text())

    def get(self, url: str) -> str | None:
        return self._data.get(url)

    def set(self, url: str, hash_: str) -> None:
        self._data[url] = hash_

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2))
