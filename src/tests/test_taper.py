"""
Test module for the Taper class using Hypothesis and pytest.
"""

import pytest
from hypothesis import assume, given

from capistry.taper import Taper

from .util import strategy as st


def test_default_constructor():
    """Test default constructor creates zero taper."""
    taper = Taper()
    assert taper.front == 0.0
    assert taper.back == 0.0
    assert taper.left == 0.0
    assert taper.right == 0.0


@given(st.floats())
def test_uniform_constructor(value):
    """Test uniform constructor sets all sides to same value."""
    taper = Taper.uniform(value)
    assert taper.front == value
    assert taper.back == value
    assert taper.left == value
    assert taper.right == value


@given(st.tapers())
def test_equality(taper: Taper):
    """Test that Taper equality works correctly."""
    assert taper == taper

    identical = Taper(front=taper.front, back=taper.back, left=taper.left, right=taper.right)
    assert taper == identical


@given(st.tapers(), st.floats())
def test_scaled_returns_correct_values(taper: Taper, factor):
    """Test that scaled values are correctly calculated."""
    scaled = taper.scaled(factor)
    assert scaled.front == pytest.approx(taper.front * factor)
    assert scaled.back == pytest.approx(taper.back * factor)
    assert scaled.left == pytest.approx(taper.left * factor)
    assert scaled.right == pytest.approx(taper.right * factor)


@given(st.tapers())
def test_scaled_by_zero(taper: Taper):
    """Test scaling by zero results in zero taper."""
    scaled = taper.scaled(0.0)
    assert scaled.front == 0.0
    assert scaled.back == 0.0
    assert scaled.left == 0.0
    assert scaled.right == 0.0


@given(st.tapers(), st.floats(), st.floats())
def test_clamp_normal(taper: Taper, min_clamp: float, max_clamp: float):
    """Test that clamped values respect min/max bounds."""
    assume(min_clamp < max_clamp)
    clamped = taper.clamp(min_clamp, max_clamp)
    assert min_clamp <= clamped.front <= max_clamp
    assert min_clamp <= clamped.back <= max_clamp
    assert min_clamp <= clamped.left <= max_clamp
    assert min_clamp <= clamped.right <= max_clamp


@given(st.tapers(), st.floats(), st.floats())
def test_clamp_inverted(taper: Taper, min_clamp: float, max_clamp: float):
    """Test clamping behavior when min > max."""
    assume(min_clamp > max_clamp)

    with pytest.raises(ValueError):
        taper.clamp(min_clamp, max_clamp)


@given(
    st.tapers(-100, 100),
    st.floats(max_value=-100, exclude_max=True),
    st.floats(min_value=100, exclude_min=True),
)
def test_clamp_outside_values(taper: Taper, min_clamp: float, max_clamp: float):
    """Test that clamping with range outside taper values changes nothing."""
    clamped = taper.clamp(min_clamp, max_clamp)
    assert clamped == taper


@given(st.tapers())
def test_str(taper: Taper):
    """Test exact string format matches expected pattern."""
    expected = f"Taper ({taper.front:.2f}, {taper.back:.2f}, {taper.left:.2f}, {taper.right:.2f})"
    assert str(taper) == expected
