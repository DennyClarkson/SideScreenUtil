from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MotionSample:
    x: float
    y: float
    scale: float


class DriftMotion:
    """Slow, smooth movement that reaches and rebounds from every edge."""

    def __init__(
        self,
        duration_seconds: float = 180.0,
        size_variation: float = 0.03,
        seed: int | None = None,
    ) -> None:
        self._random = random.Random(seed)
        self.duration_seconds = max(1.0, float(duration_seconds))
        self.size_variation = max(0.0, min(0.10, float(size_variation)))
        self._started_at = time.monotonic()
        self._randomize_phases()

    def configure(self, duration_seconds: float, size_variation: float) -> None:
        self.duration_seconds = max(1.0, float(duration_seconds))
        self.size_variation = max(0.0, min(0.10, float(size_variation)))

    def reset(self, now: float | None = None) -> None:
        self._started_at = time.monotonic() if now is None else now
        self._randomize_phases()

    def sample(self, now: float | None = None) -> MotionSample:
        current = time.monotonic() if now is None else now
        elapsed = max(0.0, current - self._started_at)
        phase = elapsed / self.duration_seconds * math.tau
        return MotionSample(
            x=self._edge_bounce(phase + self._phase_x),
            y=self._edge_bounce(phase * 0.73 + self._phase_y),
            scale=1.0 + self.size_variation * math.sin(phase * 0.41 + self._phase_scale),
        )

    def _randomize_phases(self) -> None:
        self._phase_x = self._random.uniform(0.0, math.tau)
        self._phase_y = self._random.uniform(0.0, math.tau)
        self._phase_scale = self._random.uniform(0.0, math.tau)

    @staticmethod
    def _edge_bounce(phase: float) -> float:
        return 0.5 + 0.5 * math.sin(phase)
