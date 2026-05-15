"""Trial-boundary state machine driven by /aic_model/transition_event.

Engine sequence per session (aic_engine.cpp:1531-1567, 1635-1648):

  configure (once at startup) -> inactive
  --- trial 1 ---
  activate                    -> active
  ... trial runs ...
  deactivate                  -> inactive   (reset_after_trial)
  --- trial 2 ---
  activate                    -> active
  ... trial runs ...
  deactivate                  -> inactive
  ...

So we count ACTIVATE events to map to the engine's trial sequence (1-based).
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Callable, Optional


_LOG = logging.getLogger("recorder.boundary")


# lifecycle_msgs primary state IDs (from lifecycle_msgs/msg/State).
PRIMARY_STATE_UNCONFIGURED = 1
PRIMARY_STATE_INACTIVE = 2
PRIMARY_STATE_ACTIVE = 3
PRIMARY_STATE_FINALIZED = 4


class RecorderState(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"


class BoundaryDetector:
    """State machine. Translates raw TransitionEvent messages into
    on_trial_start(trial_index_1based) / on_trial_end() callbacks."""

    def __init__(
        self,
        on_trial_start: Callable[[int], None],
        on_trial_end: Callable[[], None],
    ):
        self._on_trial_start = on_trial_start
        self._on_trial_end = on_trial_end
        self._state = RecorderState.IDLE
        self._trial_counter = 0  # incremented per ACTIVATE

    @property
    def state(self) -> RecorderState:
        return self._state

    @property
    def current_trial_index(self) -> int:
        """1-based trial index (matches engine's "Trial X/N" logging and the
        trial_key naming in session_yaml.py). 0 means no trial has started."""
        return self._trial_counter

    def handle_transition(self, goal_state_id: int, goal_state_label: str) -> None:
        """Called for each /aic_model/transition_event."""
        if goal_state_id == PRIMARY_STATE_ACTIVE:
            if self._state == RecorderState.RECORDING:
                _LOG.warning(
                    "received ACTIVE while already RECORDING (trial %d) — "
                    "treating as restart",
                    self._trial_counter,
                )
                self._on_trial_end()
            self._trial_counter += 1
            self._state = RecorderState.RECORDING
            _LOG.info("trial start: index=%d", self._trial_counter)
            self._on_trial_start(self._trial_counter)
            return

        if goal_state_id == PRIMARY_STATE_INACTIVE:
            if self._state == RecorderState.RECORDING:
                _LOG.info("trial end: index=%d", self._trial_counter)
                self._state = RecorderState.IDLE
                self._on_trial_end()
            else:
                # First INACTIVE (after configure) — engine just transitioned model
                # from unconfigured to inactive; not a trial end.
                _LOG.info("ignoring INACTIVE transition while IDLE (initial configure)")
            return

        # Other states (unconfigured, finalized) are session-level, not per-trial.
        _LOG.info(
            "ignoring transition to %s (id=%d)", goal_state_label, goal_state_id
        )
