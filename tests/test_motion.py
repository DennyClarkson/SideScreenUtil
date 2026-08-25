import math

from sidescreen.motion import DriftMotion


def test_motion_samples_stay_in_bounds() -> None:
    motion = DriftMotion(duration_seconds=10, size_variation=0.05, seed=7)
    motion.reset(now=100.0)
    for offset in range(101):
        sample = motion.sample(now=100.0 + offset)
        assert 0.0 <= sample.x <= 1.0
        assert 0.0 <= sample.y <= 1.0
        assert 0.95 <= sample.scale <= 1.05


def test_motion_is_continuous_at_segment_boundary() -> None:
    motion = DriftMotion(duration_seconds=10, size_variation=0.03, seed=11)
    motion.reset(now=20.0)
    before = motion.sample(now=29.999999)
    after = motion.sample(now=30.0)
    assert abs(before.x - after.x) < 0.001
    assert abs(before.y - after.y) < 0.001
    assert abs(before.scale - after.scale) < 0.001


def test_edge_bounce_reaches_both_edges_and_reverses() -> None:
    at_left = DriftMotion._edge_bounce(-math.pi / 2)
    before_right = DriftMotion._edge_bounce(math.pi / 2 - 0.01)
    at_right = DriftMotion._edge_bounce(math.pi / 2)
    after_right = DriftMotion._edge_bounce(math.pi / 2 + 0.01)

    assert at_left == 0.0
    assert at_right == 1.0
    assert before_right < at_right
    assert after_right < at_right
