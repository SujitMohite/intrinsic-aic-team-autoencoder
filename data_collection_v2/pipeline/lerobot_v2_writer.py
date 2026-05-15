"""LeRobot v2 dataset emitter.

Layout produced:

  <root>/
  ├── meta/
  │   ├── info.json
  │   ├── episodes.jsonl
  │   ├── tasks.jsonl
  │   └── stats.json          (computed at session finalization)
  ├── data/chunk-000/
  │   ├── episode_000000.parquet
  │   └── ...
  └── aux/
      └── episode_000000.parquet   (ground-truth poses; not consumed by lerobot-train)

Per-episode parquet columns (LeRobot v2 conventions):
  observation.images.{left,center,right}  : JPG bytes (image dtype)
  observation.state                       : float32[25]
  observation.wrench                      : float32[6]
  action                                  : float32[13]
  timestamp                               : float64    (seconds from episode start, sim time)
  frame_index                             : int64      (0..len-1 within episode)
  episode_index                           : int64
  index                                   : int64      (global frame counter)
  task_index                              : int64
  next.done                               : bool       (True only on last frame)
  next.reward                             : float32    (1.0 on insertion-event frame, else 0.0)
  next.success                            : bool       (True on final frame iff insertion fired)

Concurrency: each WriteSession instance is owned by ONE writer (the recorder node).
Per-episode parquet writes are atomic. The episodes.jsonl + tasks.jsonl files are
append-only with fsync. info.json is rewritten at finalize().

NOTE: schema details are based on LeRobot v2 spec documented at
https://github.com/huggingface/lerobot. Cross-check the installed version
(`pixi run python -c 'import lerobot; print(lerobot.__version__)'`) and adjust
the keys in _FEATURES if v0.5.x rejects this layout. See the plan §11 open items.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


_LOG = logging.getLogger("pipeline.lerobot_v2_writer")


# Feature dimensions. Keep in sync with the row builder in
# recorder/data_collection_v2_recorder/lerobot_row.py.
STATE_DIM = 25   # tcp_pose(7) + tcp_velocity(6) + joint_position(6) + joint_velocity(6)
WRENCH_DIM = 6
ACTION_DIM = 13  # twist_lin(3) + twist_ang(3) + stiffness_diag(6) + traj_mode(1)


def _feature_spec(camera_hw: tuple[int, int]) -> dict[str, Any]:
    h, w = camera_hw
    return {
        "observation.images.left": {
            "dtype": "image",
            "shape": [h, w, 3],
            "names": ["height", "width", "channel"],
        },
        "observation.images.center": {
            "dtype": "image",
            "shape": [h, w, 3],
            "names": ["height", "width", "channel"],
        },
        "observation.images.right": {
            "dtype": "image",
            "shape": [h, w, 3],
            "names": ["height", "width", "channel"],
        },
        "observation.state": {
            "dtype": "float32",
            "shape": [STATE_DIM],
            "names": [
                "tcp_pos_x", "tcp_pos_y", "tcp_pos_z",
                "tcp_ori_x", "tcp_ori_y", "tcp_ori_z", "tcp_ori_w",
                "tcp_vel_lin_x", "tcp_vel_lin_y", "tcp_vel_lin_z",
                "tcp_vel_ang_x", "tcp_vel_ang_y", "tcp_vel_ang_z",
                "joint_pos_0", "joint_pos_1", "joint_pos_2",
                "joint_pos_3", "joint_pos_4", "joint_pos_5",
                "joint_vel_0", "joint_vel_1", "joint_vel_2",
                "joint_vel_3", "joint_vel_4", "joint_vel_5",
            ],
        },
        "observation.wrench": {
            "dtype": "float32",
            "shape": [WRENCH_DIM],
            "names": ["fx", "fy", "fz", "tx", "ty", "tz"],
        },
        "action": {
            "dtype": "float32",
            "shape": [ACTION_DIM],
            "names": [
                "twist_lin_x", "twist_lin_y", "twist_lin_z",
                "twist_ang_x", "twist_ang_y", "twist_ang_z",
                "stiffness_x", "stiffness_y", "stiffness_z",
                "stiffness_rx", "stiffness_ry", "stiffness_rz",
                "traj_mode",
            ],
        },
        "timestamp": {"dtype": "float64", "shape": [1]},
        "frame_index": {"dtype": "int64", "shape": [1]},
        "episode_index": {"dtype": "int64", "shape": [1]},
        "index": {"dtype": "int64", "shape": [1]},
        "task_index": {"dtype": "int64", "shape": [1]},
        "next.done": {"dtype": "bool", "shape": [1]},
        "next.reward": {"dtype": "float32", "shape": [1]},
        "next.success": {"dtype": "bool", "shape": [1]},
    }


_CHUNK_SIZE = 1000
DATA_PATH_TEMPLATE = "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet"


def _chunk_for(episode_index: int) -> int:
    return episode_index // _CHUNK_SIZE


@dataclass
class WriteSession:
    """Stateful writer. One per session; opens at session start, closes at finalize."""

    root: Path
    fps: int = 20
    camera_hw: tuple[int, int] = (256, 256)
    robot_type: str = "ur5e_aic"
    codebase_version: str = "v2.0"

    # Running counters — restored from disk if root already exists.
    next_episode_index: int = field(default=0, init=False)
    global_frame_index: int = field(default=0, init=False)
    task_to_index: dict[str, int] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        (self.root / "meta").mkdir(parents=True, exist_ok=True)
        (self.root / "data" / "chunk-000").mkdir(parents=True, exist_ok=True)
        (self.root / "aux").mkdir(parents=True, exist_ok=True)
        self._restore_state()

    def _restore_state(self) -> None:
        """If the dataset root already has content, load counters so we can resume."""
        ep_path = self.root / "meta" / "episodes.jsonl"
        if ep_path.exists():
            n_eps = 0
            n_frames = 0
            with open(ep_path) as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        row = json.loads(ln)
                        n_eps = max(n_eps, int(row.get("episode_index", -1)) + 1)
                        n_frames += int(row.get("length", 0))
                    except json.JSONDecodeError:
                        continue
            self.next_episode_index = n_eps
            self.global_frame_index = n_frames
        tk_path = self.root / "meta" / "tasks.jsonl"
        if tk_path.exists():
            with open(tk_path) as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        row = json.loads(ln)
                        self.task_to_index[row["task"]] = int(row["task_index"])
                    except (json.JSONDecodeError, KeyError):
                        continue

    def _ensure_task_index(self, task: str) -> int:
        if task in self.task_to_index:
            return self.task_to_index[task]
        idx = len(self.task_to_index)
        self.task_to_index[task] = idx
        tk_path = self.root / "meta" / "tasks.jsonl"
        with open(tk_path, "a") as f:
            f.write(json.dumps({"task_index": idx, "task": task}) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return idx

    def write_episode(
        self,
        rows: list[dict[str, Any]],
        task: str,
        aux_rows: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Write one episode.

        Args:
          rows: list of LeRobot v2 dicts. MUST contain the columns named in _FEATURES,
                EXCEPT episode_index / index / next.done / next.success which this method
                fills in. The caller fills in everything else, including next.reward.
          task: human-readable task name; mapped to task_index.
          aux_rows: optional ground-truth supervision rows, written to aux/episode_NNNNNN.parquet.

        Returns: episode meta dict (episode_index, length, tasks, file path).
        """
        if not rows:
            raise ValueError("write_episode called with empty rows list")

        episode_index = self.next_episode_index
        task_index = self._ensure_task_index(task)
        length = len(rows)
        chunk = _chunk_for(episode_index)

        # Fill in per-row fields the caller doesn't own.
        for local_i, row in enumerate(rows):
            row["episode_index"] = int(episode_index)
            row["task_index"] = int(task_index)
            row["index"] = int(self.global_frame_index + local_i)
            row.setdefault("frame_index", int(local_i))
            row["next.done"] = bool(local_i == length - 1)
            # next.success is set on the LAST frame iff caller marked any frame as
            # insertion-event positive. Caller passes per-row "_insertion_seen" sentinel
            # we drop after consuming.
            if local_i == length - 1:
                seen = any(r.pop("_insertion_seen", False) for r in rows)
                row["next.success"] = bool(seen)
            else:
                row.pop("_insertion_seen", None)
                row["next.success"] = False
            row.setdefault("next.reward", 0.0)

        ep_dir = self.root / "data" / f"chunk-{chunk:03d}"
        ep_dir.mkdir(parents=True, exist_ok=True)
        out_path = ep_dir / f"episode_{episode_index:06d}.parquet"

        table = pa.Table.from_pylist(rows)
        pq.write_table(table, str(out_path), compression="snappy")

        if aux_rows:
            aux_path = self.root / "aux" / f"episode_{episode_index:06d}.parquet"
            aux_table = pa.Table.from_pylist(aux_rows)
            pq.write_table(aux_table, str(aux_path), compression="snappy")

        # Append episodes.jsonl atomically.
        ep_record = {
            "episode_index": int(episode_index),
            "tasks": [task],
            "length": int(length),
        }
        ep_jsonl = self.root / "meta" / "episodes.jsonl"
        with open(ep_jsonl, "a") as f:
            f.write(json.dumps(ep_record) + "\n")
            f.flush()
            os.fsync(f.fileno())

        # Bump counters AFTER successful write so a crash mid-write doesn't desync.
        self.next_episode_index += 1
        self.global_frame_index += length

        _LOG.info(
            "wrote episode %d (%d frames, task=%s) -> %s",
            episode_index,
            length,
            task,
            out_path.relative_to(self.root),
        )

        return {
            "episode_index": int(episode_index),
            "length": int(length),
            "task": task,
            "parquet_path": str(out_path.relative_to(self.root)),
        }

    def finalize(self) -> None:
        """Write meta/info.json and meta/stats.json. Call at session end."""
        info = {
            "codebase_version": self.codebase_version,
            "robot_type": self.robot_type,
            "total_episodes": int(self.next_episode_index),
            "total_frames": int(self.global_frame_index),
            "total_tasks": int(len(self.task_to_index)),
            "total_videos": 0,
            "total_chunks": int(max(1, _chunk_for(max(0, self.next_episode_index - 1)) + 1)),
            "chunks_size": _CHUNK_SIZE,
            "fps": int(self.fps),
            "splits": {"train": f"0:{self.next_episode_index}"},
            "data_path": DATA_PATH_TEMPLATE,
            "features": _feature_spec(self.camera_hw),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        info_path = self.root / "meta" / "info.json"
        tmp = info_path.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump(info, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, info_path)

        stats = self._compute_stats()
        stats_path = self.root / "meta" / "stats.json"
        tmp = stats_path.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump(stats, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, stats_path)
        _LOG.info(
            "finalized lerobot_v2 dataset at %s (episodes=%d frames=%d)",
            self.root,
            self.next_episode_index,
            self.global_frame_index,
        )

    def _compute_stats(self) -> dict[str, Any]:
        """Compute mean/std/min/max for the numeric features by scanning all parquet
        files. Images are skipped (the convention is to normalize them via the encoder
        front-end, not via dataset stats)."""
        numeric_cols = ["observation.state", "observation.wrench", "action"]
        accum: dict[str, dict[str, Any]] = {}
        for col in numeric_cols:
            accum[col] = {
                "sum": None,
                "sum_sq": None,
                "min": None,
                "max": None,
                "n": 0,
            }

        data_root = self.root / "data"
        for parquet in sorted(data_root.rglob("episode_*.parquet")):
            try:
                t = pq.read_table(str(parquet), columns=numeric_cols)
            except Exception as e:  # noqa: BLE001
                _LOG.warning("stats: failed to read %s: %s", parquet, e)
                continue
            for col in numeric_cols:
                if col not in t.column_names:
                    continue
                arr = t.column(col).to_pylist()
                if not arr:
                    continue
                import numpy as np  # local import; numpy is part of pixi env

                A = np.asarray(arr, dtype=np.float64)
                if accum[col]["sum"] is None:
                    accum[col]["sum"] = np.zeros(A.shape[1], dtype=np.float64)
                    accum[col]["sum_sq"] = np.zeros(A.shape[1], dtype=np.float64)
                    accum[col]["min"] = A.min(axis=0)
                    accum[col]["max"] = A.max(axis=0)
                else:
                    accum[col]["min"] = np.minimum(accum[col]["min"], A.min(axis=0))
                    accum[col]["max"] = np.maximum(accum[col]["max"], A.max(axis=0))
                accum[col]["sum"] += A.sum(axis=0)
                accum[col]["sum_sq"] += (A ** 2).sum(axis=0)
                accum[col]["n"] += A.shape[0]

        import numpy as np  # noqa

        stats: dict[str, Any] = {}
        for col, a in accum.items():
            if a["sum"] is None or a["n"] == 0:
                continue
            n = a["n"]
            mean = a["sum"] / n
            var = (a["sum_sq"] / n) - (mean ** 2)
            std = np.sqrt(np.maximum(var, 0.0))
            stats[col] = {
                "mean": mean.tolist(),
                "std": std.tolist(),
                "min": a["min"].tolist(),
                "max": a["max"].tolist(),
                "count": int(n),
            }
        return stats
