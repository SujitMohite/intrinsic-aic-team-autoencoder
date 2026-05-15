"""Append-only JSONL manifest.

One JSON object per line, written atomically. Restart-resilient: reading the manifest
gives the set of seeds we've already collected.

Lifted verbatim from data_collection/pipeline/manifest.py.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Manifest:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _atomic_append(self, line: str) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)
            if not line.endswith("\n"):
                f.write("\n")
            f.flush()
            os.fsync(f.fileno())

    def append(self, row: dict[str, Any]) -> None:
        row = {**row, "completed_at_iso": datetime.now(timezone.utc).isoformat()}
        self._atomic_append(json.dumps(row, default=str))

    def read_completed_seeds(self) -> set[int]:
        seeds: set[int] = set()
        if not self.path.exists():
            return seeds
        with open(self.path, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    row = json.loads(ln)
                    s = row.get("trial_config", {}).get("seed")
                    if isinstance(s, int):
                        seeds.add(s)
                except (json.JSONDecodeError, AttributeError):
                    continue
        return seeds

    def read_all(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.path.exists():
            return rows
        with open(self.path, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rows.append(json.loads(ln))
                except json.JSONDecodeError:
                    continue
        return rows

    def count(self) -> int:
        if not self.path.exists():
            return 0
        with open(self.path, "r", encoding="utf-8") as f:
            return sum(1 for ln in f if ln.strip())

    def rewrite(self, rows: list[dict[str, Any]]) -> None:
        """Rewrite the manifest in-place. Used by session finalization to backfill
        scoring data from the engine's session-end scoring.yaml."""
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, default=str))
                f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)
