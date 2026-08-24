import numpy as np

from sidescreen.filters import FilterConfig, apply_filter


def test_original_filter_applies_brightness() -> None:
    frame = np.full((2, 3, 4), 200, dtype=np.uint8)
    result = apply_filter(frame, FilterConfig(brightness=0.5))
    assert np.all(result[..., :3] == 100)
    assert np.all(result[..., 3] == 255)


def test_edge_filter_keeps_uniform_image_black() -> None:
    frame = np.full((8, 8, 4), 200, dtype=np.uint8)
    result = apply_filter(frame, FilterConfig(style="edge", brightness=1.0))
    assert np.all(result[..., :3] == 0)


def test_cycle_filter_changes_color_over_time() -> None:
    frame = np.full((2, 2, 4), 255, dtype=np.uint8)
    config = FilterConfig(style="mono_cycle", brightness=1.0, hue_cycle_seconds=120)
    first = apply_filter(frame, config, now=0.0)
    second = apply_filter(frame, config, now=40.0)
    assert not np.array_equal(first[..., :3], second[..., :3])


def test_edge_filter_uses_soft_ramp_for_text_antialiasing() -> None:
    frame = np.zeros((12, 20, 4), dtype=np.uint8)
    frame[..., 3] = 255
    frame[:, 7:13, :3] = 35
    result = apply_filter(
        frame,
        FilterConfig(style="edge", brightness=1.0, accent_color="#ffffff", edge_threshold=18),
    )
    values = result[..., 0]
    assert np.any((values > 0) & (values < 255))


def test_edge_thickness_grows_character_contours_inward() -> None:
    frame = np.zeros((20, 20, 4), dtype=np.uint8)
    frame[..., 3] = 255
    frame[5:15, 8:12, :3] = 255
    thin = apply_filter(frame, FilterConfig(style="edge", brightness=1.0, edge_thickness=1))
    thick = apply_filter(frame, FilterConfig(style="edge", brightness=1.0, edge_thickness=3))
    assert np.count_nonzero(thick[..., 0]) > np.count_nonzero(thin[..., 0])
    assert np.all(thick[:5, :, :3] == 0)
    assert np.all(thick[15:, :, :3] == 0)
    assert np.all(thick[:, :8, :3] == 0)
    assert np.all(thick[:, 12:, :3] == 0)


def test_edge_filter_places_contour_on_brighter_side() -> None:
    frame = np.zeros((9, 9, 4), dtype=np.uint8)
    frame[..., 3] = 255
    frame[2:7, 2:7, :3] = 180
    result = apply_filter(
        frame,
        FilterConfig(
            style="edge",
            brightness=1.0,
            accent_color="#ffffff",
            edge_threshold=18,
            edge_thickness=1,
        ),
    )
    lit = result[..., 0] > 0
    assert np.any(lit[2:7, 2:7])
    assert not np.any(lit & (frame[..., 0] == 0))
