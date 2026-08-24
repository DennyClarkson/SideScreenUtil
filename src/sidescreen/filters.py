from __future__ import annotations

import colorsys
import time
from dataclasses import dataclass

import numpy as np

FILTER_LABEL_KEYS = {
    "original": "filter.original",
    "grayscale": "filter.grayscale",
    "mono": "filter.mono",
    "mono_cycle": "filter.mono_cycle",
    "edge": "filter.edge",
    "edge_cycle": "filter.edge_cycle",
}


@dataclass(frozen=True, slots=True)
class FilterConfig:
    style: str = "original"
    brightness: float = 0.65
    accent_color: str = "#22d3ee"
    hue_cycle_seconds: int = 120
    edge_threshold: int = 18
    edge_thickness: int = 2

    @property
    def animated(self) -> bool:
        return self.style in {"mono_cycle", "edge_cycle"}


def apply_filter(
    frame: np.ndarray,
    config: FilterConfig,
    now: float | None = None,
) -> np.ndarray:
    """Apply an OLED-oriented visual filter to a BGRA uint8 frame."""
    if frame.ndim != 3 or frame.shape[2] < 4:
        raise ValueError("Expected a BGRA image")
    source = frame[..., :4]
    brightness = min(1.0, max(0.1, float(config.brightness)))
    style = config.style

    if style == "original":
        output = source.copy()
        output[..., :3] = np.multiply(output[..., :3], brightness).astype(np.uint8)
        output[..., 3] = 255
        return output

    gray = _grayscale(source)
    if style == "grayscale":
        value = np.multiply(gray, brightness).astype(np.uint8)
        output = np.empty_like(source)
        output[..., 0] = value
        output[..., 1] = value
        output[..., 2] = value
        output[..., 3] = 255
        return output

    current = time.monotonic() if now is None else now
    accent = _accent_bgr(config, current)
    if style in {"edge", "edge_cycle"}:
        intensity = _edge_map(gray, config.edge_threshold, config.edge_thickness)
    else:
        intensity = gray
    intensity = intensity.astype(np.float32) / 255.0 * brightness
    output = np.zeros_like(source)
    for channel, value in enumerate(accent):
        output[..., channel] = np.multiply(intensity, value).astype(np.uint8)
    output[..., 3] = 255
    return output


def _grayscale(frame: np.ndarray) -> np.ndarray:
    blue = frame[..., 0].astype(np.float32)
    green = frame[..., 1].astype(np.float32)
    red = frame[..., 2].astype(np.float32)
    return np.clip(blue * 0.114 + green * 0.587 + red * 0.299, 0, 255).astype(np.uint8)


def _edge_map(gray: np.ndarray, threshold: int, thickness: int = 2) -> np.ndarray:
    """Return antialiased contours that expand only into the brighter region."""
    source = gray.astype(np.int16)
    neighbor_minimum = source.copy()
    neighbor_minimum[1:, :] = np.minimum(neighbor_minimum[1:, :], source[:-1, :])
    neighbor_minimum[:-1, :] = np.minimum(neighbor_minimum[:-1, :], source[1:, :])
    neighbor_minimum[:, 1:] = np.minimum(neighbor_minimum[:, 1:], source[:, :-1])
    neighbor_minimum[:, :-1] = np.minimum(neighbor_minimum[:, :-1], source[:, 1:])
    neighbor_minimum[1:, 1:] = np.minimum(neighbor_minimum[1:, 1:], source[:-1, :-1])
    neighbor_minimum[:-1, :-1] = np.minimum(neighbor_minimum[:-1, :-1], source[1:, 1:])
    neighbor_minimum[1:, :-1] = np.minimum(neighbor_minimum[1:, :-1], source[:-1, 1:])
    neighbor_minimum[:-1, 1:] = np.minimum(neighbor_minimum[:-1, 1:], source[1:, :-1])
    magnitude = source - neighbor_minimum

    # The one-sided gradient places the contour on the brighter side of a boundary.
    # A soft ramp keeps antialiased text strokes connected instead of producing
    # binary speckles.
    cutoff = max(4, int(threshold))
    edges = np.clip((magnitude.astype(np.float32) - cutoff) * 4.2, 0, 255).astype(np.uint8)
    for _ in range(max(0, min(4, int(thickness)) - 1)):
        grown = edges.copy()
        grown[1:, :] = np.maximum(
            grown[1:, :], np.where(source[1:, :] >= source[:-1, :], edges[:-1, :], 0)
        )
        grown[:-1, :] = np.maximum(
            grown[:-1, :], np.where(source[:-1, :] >= source[1:, :], edges[1:, :], 0)
        )
        grown[:, 1:] = np.maximum(
            grown[:, 1:], np.where(source[:, 1:] >= source[:, :-1], edges[:, :-1], 0)
        )
        grown[:, :-1] = np.maximum(
            grown[:, :-1], np.where(source[:, :-1] >= source[:, 1:], edges[:, 1:], 0)
        )
        edges = grown
    return edges


def _accent_bgr(config: FilterConfig, now: float) -> tuple[int, int, int]:
    if config.style in {"mono_cycle", "edge_cycle"}:
        period = max(10, config.hue_cycle_seconds)
        hue = (now % period) / period
        red, green, blue = colorsys.hsv_to_rgb(hue, 0.82, 1.0)
        return round(blue * 255), round(green * 255), round(red * 255)
    value = config.accent_color.lstrip("#")
    if len(value) != 6:
        value = "22d3ee"
    red, green, blue = (int(value[index : index + 2], 16) for index in (0, 2, 4))
    return blue, green, red
