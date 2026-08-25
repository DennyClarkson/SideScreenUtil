import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np  # noqa: E402
from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from sidescreen.motion import MotionSample  # noqa: E402
from sidescreen.overlay import MonitorOverlay  # noqa: E402


def test_bgra_frame_is_retained_without_qimage_copy() -> None:
    application = QApplication.instance() or QApplication([])
    overlay = MonitorOverlay()
    pixels = np.array([1, 2, 3, 255] * 8, dtype=np.uint8).reshape((2, 4, 4))
    overlay.set_frame(42, pixels, 4, 2)
    assert overlay.frame_sizes[42] == (4, 2)
    assert overlay._frames[42].constBits().tobytes()[:4] == bytes([1, 2, 3, 255])
    assert overlay._frame_buffers[42] is pixels
    overlay.deleteLater()
    application.processEvents()


def test_layout_edit_mode_blocks_pointer_suppression() -> None:
    application = QApplication.instance() or QApplication([])
    overlay = MonitorOverlay()
    overlay._active = True
    overlay.set_layout({42: QRectF(0.1, 0.1, 0.5, 0.5)}, animate=False)
    assert overlay.start_layout_editing()
    overlay.suppress_for_pointer()
    assert overlay.layout_editing
    assert not overlay.pointer_suppressed
    overlay.finish_layout_editing(False)
    overlay.deleteLater()
    application.processEvents()


def test_empty_sources_clear_layout_and_keep_black_canvas() -> None:
    application = QApplication.instance() or QApplication([])
    overlay = MonitorOverlay()
    overlay.set_layout({42: QRectF(0.1, 0.1, 0.5, 0.5)}, animate=False)
    overlay.set_frame(42, np.zeros((2, 4, 4), dtype=np.uint8), 4, 2)

    overlay.set_sources([])

    assert overlay.frame_sizes == {}
    assert overlay._layout_target == {}
    assert not overlay.start_layout_editing()
    overlay.deleteLater()
    application.processEvents()


def test_composition_can_touch_both_screen_edges() -> None:
    application = QApplication.instance() or QApplication([])
    overlay = MonitorOverlay()
    overlay.resize(1000, 800)
    overlay._settings.preview_scale = 0.8

    overlay._motion.sample = lambda _now: MotionSample(0.0, 0.0, 1.0)
    at_top_left = overlay._composition_rect(0.0)
    overlay._motion.sample = lambda _now: MotionSample(1.0, 1.0, 1.0)
    at_bottom_right = overlay._composition_rect(0.0)

    assert at_top_left.left() == 0.0
    assert at_top_left.top() == 0.0
    assert at_bottom_right.right() == 1000.0
    assert at_bottom_right.bottom() == 800.0
    overlay.deleteLater()
    application.processEvents()
