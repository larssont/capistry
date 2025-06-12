from typing import Any

import pytest
from build123d import Part

from tests.util.approximate import TOL_GEOMETRY_ABS


def parts(actual: Any, expected: Any):
    assert isinstance(actual, Part), f"Actual is not a Part: {type(actual)}"
    assert isinstance(expected, Part), f"Expected is not a Part: {type(expected)}"

    assert actual.volume == pytest.approx(expected.volume, rel=TOL_GEOMETRY_ABS), (
        f"Volume mismatch: {actual.volume} != {expected.volume}"
    )
    assert actual.location == expected.location, (
        f"Location mismatch:\n  actual:   {actual.location}\n  expected: {expected.location}"
    )

    diff_volume = (expected - actual).volume
    assert diff_volume == pytest.approx(0, abs=TOL_GEOMETRY_ABS), (
        f"Geometry mismatch (difference volume = {diff_volume})"
    )
