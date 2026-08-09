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
    """Slow, non-repeating movement in normalized 0..1 coordinates."""

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
        self._start = self._random_sample()
        self._target = self._random_sample()

    def configure(self, duration_seconds: float, size_variation: float) -> None:
        self.duration_seconds = max(1.0, float(duration_seconds))
        self.size_variation = max(0.0, min(0.10, float(size_variation)))

    def reset(self, now: float | None = None) -> None:
        self._started_at = time.monotonic() if now is None else now
        self._start = self._random_sample()
        self._target = self._random_sample()

    def sample(self, now: float | None = None) -> MotionSample:
        current = time.monotonic() if now is None else now
        elapsed = max(0.0, current - self._started_at)
        while elapsed >= self.duration_seconds:
            self._start = self._target
            self._target = self._random_sample()
            self._started_at += self.duration_seconds
            elapsed = max(0.0, current - self._started_at)

        progress = min(1.0, elapsed / self.duration_seconds)
        eased = 0.5 - 0.5 * math.cos(math.pi * progress)
        return MotionSample(
            x=self._lerp(self._start.x, self._target.x, eased),
            y=self._lerp(self._start.y, self._target.y, eased),
            scale=self._lerp(self._start.scale, self._target.scale, eased),
        )

    def _random_sample(self) -> MotionSample:
        variation = self.size_variation
        return MotionSample(
            x=self._random.random(),
            y=self._random.random(),
            scale=1.0 + self._random.uniform(-variation, variation),
        )

    @staticmethod
    def _lerp(start: float, end: float, amount: float) -> float:
        return start + (end - start) * amount
