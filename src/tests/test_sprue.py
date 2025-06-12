"""
Test module for the Taper class using Hypothesis and pytest.
"""

import pytest
from build123d import Plane, Rot, Vector
from hypothesis import assume, example, given, note

from capistry._math import (
    circle_area,
    cylinder_surface,
    polygon_area,
    polygon_height,
    polygon_prism_surface,
    polygon_width,
)
from capistry.sprue import Sprue, SprueCylinder, SpruePolygon

from .util import check
from .util import strategy as st


@example(SprueCylinder(), 0).xfail()
@given(st.sprues_cylinder(), st.floats(profile=st.NumProfile.GEOMETRY))
def test_create_sprue_cylinder(sprue: SprueCylinder, length: float):
    actual = sprue._create(length)

    assert actual.area == pytest.approx(cylinder_surface(sprue.diameter / 2, length))
    assert actual.volume == pytest.approx(circle_area(sprue.diameter / 2) * length)
    assert actual.location == Rot(0, 90, 90)

    bbox = actual.bounding_box()
    note(f"Sprue bounding box: {bbox}")

    assert bbox.min.to_tuple() == pytest.approx((0, -sprue.diameter / 2, -sprue.diameter))
    assert bbox.max.to_tuple() == pytest.approx((length, sprue.diameter / 2, 0))


@example(SpruePolygon(), 0).xfail()
@given(st.sprues_polygon(), st.floats(profile=st.NumProfile.GEOMETRY))
def test_create_polygon(sprue: SpruePolygon, length: float):
    actual = sprue._create(length)

    assert actual.area == pytest.approx(
        polygon_prism_surface(sprue.sides, sprue.diameter / 2, length, inradius=True)
    )
    assert actual.volume == pytest.approx(
        polygon_area(sprue.sides, sprue.diameter / 2, inradius=True) * length
    )
    assert actual.location == Rot(0, 90, 90)

    bbox = actual.bounding_box()
    note(f"Sprue bounding box: {bbox}")

    width = polygon_width(sprue.sides, sprue.diameter / 2)

    assert bbox.min.to_tuple() == pytest.approx(
        (0, -width / 2, -polygon_height(sprue.sides, sprue.diameter / 2))
    )
    assert bbox.max.to_tuple() == pytest.approx((length, width / 2, 0))


@given(st.sprues(), st.vectors(), st.vectors())
def test_between(sprue: Sprue, start: Vector, end: Vector):
    x_dir = end - start

    # Filter out too short directions parallel with the Z axis
    assume(x_dir.length > 0.01)
    assume(x_dir.cross(Vector(0, 0, 1)).length > 0.01)

    actual = sprue._between(start, end)
    expected = Plane(origin=start, x_dir=x_dir) * sprue._create(x_dir.length)

    check.parts(actual, expected)


@given(st.sprues(), st.vectors(0, 0), st.vectors(0, 0))
def test_between_invalid_direction(sprue: Sprue, start: Vector, end: Vector):
    assume((end - start).length > 0.01)

    with pytest.raises(ValueError, match=r"^(Invalid direction)"):
        sprue._between(start, end)


@given(st.sprues(), st.vectors())
def test_between_too_short(sprue: Sprue, v: Vector):
    with pytest.raises(ValueError, match=r"^(Sprue segment too short)"):
        sprue._between(v, v)
