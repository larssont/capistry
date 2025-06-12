import re
from typing import Any

import pytest
from build123d import Face
from hypothesis import assume, given, note
from more_itertools import flatten

from capistry.surface import Surface
from capistry.utils import mirror_matrix, rotate_matrix
from tests.util.approximate import approx_eq, approx_ge, approx_le

from .util import strategy as st


@given(st.tensors(st.ints(-10, 10), shape=(2, st.ints(2, 10), st.ints(2, 10))))
def test_weights_adjusted(tensor: list[list[int]]):
    offsets, weights = tensor[0], tensor[1]

    surface = Surface(offsets=offsets, weights=weights)

    actual_weights = list(flatten(surface.weights))

    expected_weighs = list(flatten(weights))
    expected_diff = 1 - min(min(expected_weighs), 1)
    expected_weights = list(map(lambda w: w + expected_diff, expected_weighs))

    assert actual_weights == expected_weights
    assert all(w >= 1.0 for w in actual_weights)


@given(st.surfaces(), st.floats(min_value=-10, max_value=10))
def test_scaled(surface: Surface, factor):
    scaled = surface.scaled(factor)

    for i, row in enumerate(scaled.offsets):
        for j, v in enumerate(row):
            assert scaled.offsets[i][j] == pytest.approx(surface.offsets[i][j] * factor)


@given(st.surfaces(offset=st.floats(-10, 10)), st.floats(min_value=-10, max_value=10))
def test_normalized(surface: Surface, minimum: float):
    normalized = surface.normalized(minimum=minimum)

    actual_min = min(flatten(normalized.offsets))

    assert approx_eq(actual_min, minimum)


@given(st.ints(min_value=2, max_value=4), st.ints(min_value=2, max_value=4))
def test_flat(rows: int, cols: int):
    surface = Surface.flat(rows, cols)
    assert all(v == 0 for row in surface.offsets for v in row)


@given(
    st.tensors(shape=(st.ints(2, 10), st.ints(2, 10))),
    st.tensors(shape=(st.ints(2, 10), st.ints(2, 10)), dynamic=True),
)
def test_irregular_rows(valid: list[list[int]], invalid: list[list[int]]):
    assume(len({len(r) for r in invalid}) > 1)

    Surface(offsets=valid, weights=valid)

    cases = [
        (valid, invalid, r"All rows in 'weights' must be the same length"),
        (invalid, valid, r"All rows in 'offsets' must be the same length"),
        (invalid, invalid, r"All rows in '(offsets|weights)' must be the same length"),
    ]

    for offsets, weights, match in cases:
        with pytest.raises(ValueError, match=match):
            Surface(offsets=offsets, weights=weights)


@given(
    st.tensors(shape=(st.ints(2, 10), st.ints(2, 10))),
    st.tensors(shape=(st.ints(1, 2), st.ints(1, 2))),
)
def test_invalid_row_col_count(valid: list[list[int]], invalid: list[list[int]]):
    rows, cols = len(invalid), len(invalid[0])
    assume(min(rows, cols) < 2)

    Surface(offsets=valid, weights=valid)

    cases = [
        (invalid, valid),
        (valid, invalid),
        (invalid, invalid),
    ]

    for offsets, weights in cases:
        with pytest.raises(ValueError, match=r"must have at least 2 (rows|columns)"):
            Surface(offsets=offsets, weights=weights)


@given(
    st.tensors(shape=(st.ints(5, 10), st.ints(5, 10))),
    st.tensors(shape=(st.ints(2, 4), st.ints(2, 4))),
)
def test_invalid_weights_shape(big: list[list[int]], small: list[list[int]]):
    Surface(offsets=big, weights=big)
    Surface(offsets=small, weights=small)

    cases = [
        (small, big),
        (big, small),
    ]

    note(cases)

    for offsets, weights in cases:
        with pytest.raises(
            ValueError,
            match=r"must have the same shape as 'offsets' \(\d+x\d+\), but got \d+x\d+ instead",
        ):
            Surface(offsets=offsets, weights=weights)


@given(
    st.tensors(shape=((2, 2))),
    st.one_of(
        st.any_except(list, type(None)),
        st.tensors(value=st.any_except(list), shape=(2,)),
        st.tensors(value=st.any_except(float | int), shape=(2, 2)),
    ),
)
def test_invalid_type(valid: list[list[int]], invalid: Any):
    Surface(offsets=valid, weights=valid)

    cases = [
        (invalid, valid),
        (valid, invalid),
        (invalid, invalid),
    ]

    for offsets, weights in cases:
        with pytest.raises(TypeError):
            Surface(offsets=offsets, weights=weights)


@given(st.surfaces(), st.floats(min_value=-10, max_value=10), st.booleans(), st.booleans())
def test_tilted(surface: Surface, amount: float, horizontally: bool, ascending: bool):
    """Test that tilting applies the correct gradient formula for all combinations."""
    rows, cols = len(surface.offsets), len(surface.offsets[0])
    tilted = surface.tilted(amount, horizontally=horizontally, ascending=ascending)

    length = cols if horizontally else rows

    for i, row in enumerate(tilted.offsets):
        for j, value in enumerate(row):
            pos = j if horizontally else i
            mul = (length - 1 - pos) if ascending else pos

            expected = surface.offsets[i][j] + amount * mul
            assert value == expected


@given(st.surfaces(), st.booleans(), st.booleans())
def test_tilted_zero(surface: Surface, horizontally: bool, ascending: bool):
    """Test that tilting by zero returns unchanged offsets."""
    tilted = surface.tilted(0.0, horizontally=horizontally, ascending=ascending)

    assert tilted == surface

    for i, row in enumerate(tilted.offsets):
        for j, value in enumerate(row):
            assert value == surface.offsets[i][j]


@given(st.surfaces(), st.ints(-10, 10))
def test_rotated(surface: Surface, turns: int):
    rotated = surface.rotated(turns)

    expected_offsets = rotate_matrix(surface.offsets, turns)
    expected_weights = None
    if surface.weights is not None:
        expected_weights = rotate_matrix(surface.weights, turns)

    assert rotated.offsets == expected_offsets
    assert rotated.weights == expected_weights


@given(st.surfaces(), st.booleans(), st.booleans())
def test_mirrored(surface: Surface, horizontal: bool, include_weights: bool):
    mirrored = surface.mirrored(horizontal=horizontal, include_weights=include_weights)

    expected_offsets = mirror_matrix(surface.offsets, horizontal)
    expected_weights = surface.weights
    if expected_weights is not None and include_weights:
        expected_weights = mirror_matrix(expected_weights, horizontal)

    assert mirrored.offsets == expected_offsets
    assert mirrored.weights == expected_weights


@given(st.surfaces(), st.faces(vertices=3))
def test_insufficient_vertices(surface: Surface, face: Face):
    with pytest.raises(ValueError, match=r"4 vertices"):
        surface.form_face(face)
    with pytest.raises(ValueError, match=r"4 vertices"):
        surface._sort_corners(face.vertices())


@given(st.surfaces(), st.faces())
def test_make_face(surface: Surface, face: Face):
    offsets = list(flatten(surface.offsets))

    actual_face = surface.form_face(face)
    actual_bbox = actual_face.bounding_box()

    expected_bbox = face.bounding_box()
    expected_bbox.min.Z = actual_bbox.min.Z
    expected_bbox.max.Z = actual_bbox.max.Z

    expected_xy = (*expected_bbox.min.to_tuple()[:2], *expected_bbox.max.to_tuple()[:2])
    actual_xy = (*actual_bbox.min.to_tuple()[:2], *actual_bbox.max.to_tuple()[:2])

    assert not actual_face.is_manifold
    assert approx_eq(actual_xy, expected_xy)
    assert approx_le(actual_bbox.max.Z, max(offsets))
    assert approx_ge(actual_bbox.max.Z, min(offsets))


@given(st.surfaces())
def test_str(surface: Surface):
    assert re.fullmatch(r"Surface \(\d+x\d+\)", str(surface))
