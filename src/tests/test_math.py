from functools import partial
from math import pi

import pytest
from hypothesis import example, given

from capistry._math import (
    circle_area,
    cylinder_surface,
    divisors,
    polygon_area,
    polygon_height,
    polygon_prism_surface,
    polygon_width,
)
from tests.util.approximate import approx_eq, approx_ge

from .util import strategy as st


@example(0).xfail(raises=ValueError)
@given(st.ints(min_value=1, max_value=100_000))
def test_divisors(n):
    result = divisors(n)
    assert all(n % d == 0 for d in result)
    assert sorted(result) == result
    assert result[0] == 1 and result[-1] == n


@given(
    st.ints(min_value=-100, max_value=2),
    st.floats(min_value=0, max_value=10_000),
    st.floats(min_value=0, max_value=10_000),
    st.booleans(),
)
def test_polygon_invalid(n: int, radius: float, height: float, inradius: bool):
    funcs = [
        lambda: polygon_width(n, radius, inradius),
        lambda: polygon_height(n, radius, inradius),
        lambda: polygon_area(n, radius, inradius),
        lambda: polygon_prism_surface(n, radius, height, inradius),
    ]

    for fn in funcs:
        with pytest.raises(ValueError):
            fn()


@example(3, 0, True).xfail(raises=AssertionError)
@given(
    st.ints(min_value=3, max_value=100),
    st.floats(min_value=0.1, max_value=1e5),
    st.booleans(),
)
def test_polygon_width(n: int, radius: float, inradius: bool):
    compute = partial(polygon_width, n, radius, inradius=inradius)

    width = polygon_width(n, radius, inradius)
    assert width > 0
    assert approx_ge(width, compute(inradius=False))


@example(3, 0, True).xfail(raises=AssertionError)
@given(
    st.ints(min_value=3, max_value=100),
    st.floats(min_value=0.1, max_value=10_000),
    st.booleans(),
)
def test_polygon_height(n: int, radius: float, inradius: bool):
    compute = partial(polygon_height, n, radius, inradius=inradius)

    height = compute()

    assert height > 0
    assert approx_ge(height, compute(inradius=False))


@example(3, 0, True).xfail(raises=AssertionError)
@given(
    st.ints(min_value=3, max_value=100),
    st.floats(min_value=0.1, max_value=10_000),
    st.booleans(),
)
def test_polygon_area(n: int, radius: float, inradius: bool):
    compute = partial(polygon_area, n, radius, inradius=inradius)

    area = compute()
    assert area > 0
    assert approx_ge(area, compute(inradius=False))


@example(3, 0, 0, True).xfail()
@given(
    st.ints(min_value=3, max_value=100),
    st.floats(min_value=0.1, max_value=10_000),
    st.floats(min_value=0.1, max_value=10_000),
    st.booleans(),
)
def test_polygon_prism_surface(n: int, radius: float, height: float, inradius: bool):
    compute = partial(polygon_prism_surface, n, radius, height, inradius=inradius)

    surface = compute()

    assert surface > 0
    assert approx_ge(surface, compute(inradius=False))


@given(st.floats(), st.floats())
def test_cylinder_surface(radius: float, height: float):
    assert approx_eq(cylinder_surface(radius, height), 2 * pi * radius * (radius + height))


@given(st.floats())
def test_circle_area(radius):
    assert approx_eq(circle_area(radius), radius**2 * pi)
