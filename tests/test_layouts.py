from PySide6.QtCore import QRect

from sidescreen.layouts import grid_layout, source_relative_layout, strip_layout


def test_generated_layouts_cover_every_key() -> None:
    keys = [1, 2, 3, 4, 5]
    for layout in (grid_layout(keys), strip_layout(keys), strip_layout(keys, vertical=True)):
        assert set(layout) == set(keys)
        for rectangle in layout.values():
            assert rectangle.left() >= 0
            assert rectangle.top() >= 0
            assert rectangle.right() <= 1
            assert rectangle.bottom() <= 1


def test_source_layout_preserves_left_to_right_order() -> None:
    layout = source_relative_layout({1: QRect(100, 50, 400, 300), 2: QRect(600, 100, 300, 200)})
    assert layout[1].left() < layout[2].left()
    assert layout[1].width() > layout[2].width()
