from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class WindowInfo:
    hwnd: int
    title: str
    process_name: str = ""
    pid: int = 0

    @property
    def display_name(self) -> str:
        process = f" — {self.process_name}" if self.process_name else ""
        return f"{self.title}{process}"


@dataclass(slots=True)
class AppSettings:
    language: str = "zh_CN"
    start_with_windows: bool = False
    silent_start: bool = False
    screen_id: str = ""
    preview_scale: float = 0.72
    move_seconds: int = 180
    size_variation: float = 0.03
    capture_fps: int = 12
    limit_capture_resolution: bool = True
    blank_every_minutes: int = 30
    blank_seconds: int = 30
    layout_mode: str = "source"
    filter_style: str = "original"
    brightness: float = 0.65
    accent_color: str = "#22d3ee"
    hue_cycle_seconds: int = 120
    edge_threshold: int = 18
    edge_thickness: int = 2

    def normalized(self) -> AppSettings:
        return AppSettings(
            language=str(self.language or "zh_CN"),
            start_with_windows=bool(self.start_with_windows),
            silent_start=bool(self.silent_start),
            screen_id=str(self.screen_id),
            preview_scale=min(0.90, max(0.20, float(self.preview_scale))),
            move_seconds=min(900, max(30, int(self.move_seconds))),
            size_variation=min(0.10, max(0.0, float(self.size_variation))),
            capture_fps=min(30, max(5, int(self.capture_fps))),
            limit_capture_resolution=bool(self.limit_capture_resolution),
            blank_every_minutes=min(240, max(0, int(self.blank_every_minutes))),
            blank_seconds=min(300, max(5, int(self.blank_seconds))),
            layout_mode=(
                str(self.layout_mode)
                if str(self.layout_mode) in {"source", "grid", "horizontal", "vertical", "manual"}
                else "source"
            ),
            filter_style=(
                str(self.filter_style)
                if str(self.filter_style)
                in {"original", "grayscale", "mono", "mono_cycle", "edge", "edge_cycle"}
                else "original"
            ),
            brightness=min(1.0, max(0.10, float(self.brightness))),
            accent_color=(
                str(self.accent_color) if _is_hex_color(str(self.accent_color)) else "#22d3ee"
            ),
            hue_cycle_seconds=min(600, max(10, int(self.hue_cycle_seconds))),
            edge_threshold=min(120, max(4, int(self.edge_threshold))),
            edge_thickness=min(4, max(1, int(self.edge_thickness))),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self.normalized())

    @classmethod
    def from_dict(cls, raw: object) -> AppSettings:
        if not isinstance(raw, dict):
            return cls()
        allowed = cls.__dataclass_fields__.keys()
        values = {key: value for key, value in raw.items() if key in allowed}
        try:
            return cls(**values).normalized()
        except (TypeError, ValueError):
            return cls()


def _is_hex_color(value: str) -> bool:
    if len(value) != 7 or not value.startswith("#"):
        return False
    try:
        int(value[1:], 16)
        return True
    except ValueError:
        return False
