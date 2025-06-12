import math
from math import sqrt

from build123d import *
from hypothesis import given
from ocp_vscode import *

from capistry import *
from tests.util.approximate import approx_eq, approx_ge, approx_le
from tests.util.strategy import *


def is_stem_valid(stem: Stem):
    """Asserts that the given Stem object meets all criterias."""

    assert stem.area > 0, f"Invalid stem: area must be > 0, got {stem.area}"
    assert stem.volume > 0, f"Invalid stem: volume must be > 0, got {stem.volume}"
    assert stem.is_manifold, "Invalid stem: not a manifold geometry"
    assert stem.is_valid(), "Invalid stem: failed stem.is_valid() check"

    expected_location = Location()
    assert stem.location == expected_location, (
        f"Invalid stem: location must be {expected_location}, got {stem.location}"
    )


@given(stems())
def test_valid(stem: Stem):
    is_stem_valid(stem)


@given(stems_mx(fillet=False))
def test_mx_geometry(stem: MXStem):
    actual_min = stem.bounding_box().min
    actual_max = stem.bounding_box().max

    r = stem.cylinder_radius
    q = stem.cross_width
    w = stem.cylinder_radius

    # If the cross cutout goes beyond the cylinder, adjust width
    if stem.cross_length > r * 2:
        w = 2 * sqrt(math.pow(r, 2) - math.pow(q / 2, 2)) / 2

    is_stem_valid(stem)
    assert not stem.is_inside((0, 0, 0))

    assert approx_le(stem.volume, stem.cylinder_height * stem.cylinder_radius**2 * pi)
    assert approx_eq(actual_min, (-w, -w, 0))
    assert approx_eq(actual_max, (w, w, stem.cylinder_height))
    assert approx_eq(stem.center(center_of=CenterOf.BOUNDING_BOX), (0, 0, stem.cylinder_height / 2))


@given(stems_choc(fillet=False))
def test_choc_geometry(stem: ChocStem):
    actual_min = stem.bounding_box().min
    actual_max = stem.bounding_box().max

    expected_x = (stem.leg_spacing + stem.leg_width) / 2
    expected_y = stem.leg_length / 2
    if stem.include_cross:
        expected_x = max(expected_x, (stem.cross_spacing + stem.cross_width / 2))
        expected_y = max(expected_y, stem.cross_length / 2)
    expected_z = max(stem.cross_height, stem.leg_height)

    expected_volume = 2 * stem.leg_height * stem.leg_length * stem.leg_width

    # Exclude a simplified volume of the arched legs
    if stem.include_arc:
        expected_volume -= expected_volume * stem.arc_length_ratio * stem.arc_width_ratio

    is_stem_valid(stem)

    assert stem.is_inside((-stem.leg_spacing / 2, 0, stem.leg_height))
    assert stem.is_inside((stem.leg_spacing / 2, 0, stem.leg_height))
    assert stem.is_inside((0, 0, stem.cross_height)) == stem.include_cross

    assert approx_ge(stem.volume, expected_volume)
    assert approx_eq(actual_min, (-expected_x, -expected_y, 0))
    assert approx_eq(actual_max, (expected_x, expected_y, expected_z))
    assert approx_eq(stem.center(center_of=CenterOf.BOUNDING_BOX), (0, 0, expected_z / 2))
