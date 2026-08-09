import numpy as np

from sidescreen.capture import _compact_frame


def test_compact_frame_caps_persistent_pixel_count() -> None:
    frame = np.zeros((1800, 2600, 4), dtype=np.uint8)
    compact = _compact_frame(frame)
    assert compact.shape[0] * compact.shape[1] <= 1_005_000
    assert max(compact.shape[:2]) <= 1600
    assert compact.flags.c_contiguous


def test_compact_frame_preserves_full_resolution_when_limit_is_off() -> None:
    frame = np.zeros((1800, 2600, 4), dtype=np.uint8)
    full = _compact_frame(frame, limit_resolution=False)
    assert full.shape == frame.shape
    assert full is not frame
    assert full.flags.owndata
