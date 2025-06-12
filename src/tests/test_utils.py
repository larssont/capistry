from random import Random

from hypothesis import example, given

from capistry.utils import spaced_points

from .util import strategy as st
from .util.approximate import approx_ge


@example(Random(), 0, 0, 0, 0)
@example(Random(), 10, 0, 1, 0.11).xfail(raises=ValueError)
@example(Random(), 10, 1, 0, 0).xfail(raises=ValueError)
@given(st.randoms(), st.ints(1, 10), st.floats(0, 1), st.floats(2, 3), st.floats(0, 0.05))
def test_spaced_points(rand: Random, n: int, start: float, end: float, tol: float):
    points = spaced_points(n=n, start=start, end=end, rand=rand, tolerance=tol)

    assert len(points) == n

    sorted_points = sorted(points)

    # Assert all points are within [start, end] range
    for p in sorted_points:
        assert start <= p <= end, f"Point {p} is out of range [{start}, {end}]"

    # Assert minimum spacing between consecutive points
    for a, b in zip(sorted_points, sorted_points[1:]):
        assert approx_ge((b - a), tol)
