import math
import operator
from collections.abc import Iterable
from typing import Iterable

MIN_GEOMETRY_VALUE = 1e-4
MAX_GEOMETRY_VALUE = 1000
TOL_GEOMETRY_ABS = 1e-6
TOL_GEOMETRY_REL = 1e-10


def _is_iterable(obj):
    """Check if obj is iterable but not a string/bytes."""
    return isinstance(obj, Iterable) and not isinstance(obj, (str, bytes))


def _approx_compare(actual, expected, op, *, rel, abs_, allow_approx_eq=True):
    """
    Compare actual and expected (scalars or iterables) with approximate tolerance.

    If allow_approx_eq is True, approximate equality (math.isclose) is allowed.
    Otherwise, strict comparison via op is required.

    Raises AssertionError if iterables have different lengths or types mismatch.
    """
    actual_is_iter = _is_iterable(actual)
    expected_is_iter = _is_iterable(expected)

    if actual_is_iter and expected_is_iter:
        try:
            pairs = zip(actual, expected, strict=True)
        except ValueError:
            raise AssertionError(
                f"Length mismatch between actual and expected iterables: "
                f"{len(actual)} != {len(expected)}"
            )
        for a, e in pairs:
            if not (
                op(a, e) or (allow_approx_eq and math.isclose(a, e, rel_tol=rel, abs_tol=abs_))
            ):
                return False
        return True

    if actual_is_iter != expected_is_iter:
        raise AssertionError(
            f"Cannot compare iterable with non-iterable: actual_is_iter={actual_is_iter}, "
            f"expected_is_iter={expected_is_iter}"
        )

    # Compare scalars
    return op(actual, expected) or (
        allow_approx_eq and math.isclose(actual, expected, rel_tol=rel, abs_tol=abs_)
    )


def approx_eq(actual, expected, *, rel=TOL_GEOMETRY_REL, abs_=TOL_GEOMETRY_ABS):
    """Assert actual approximately equals expected."""
    if not _approx_compare(actual, expected, operator.eq, rel=rel, abs_=abs_):
        raise AssertionError(
            f"Expected {actual} ≈ {expected} (rel={rel:.1e}, abs={abs_:.1e}), but it was not."
        )
    return True


def approx_ge(actual, expected, *, rel=TOL_GEOMETRY_REL, abs_=TOL_GEOMETRY_ABS):
    """Assert actual is approximately greater than or equal to expected."""
    if not (
        _approx_compare(actual, expected, operator.gt, rel=rel, abs_=abs_, allow_approx_eq=False)
        or _approx_compare(actual, expected, operator.eq, rel=rel, abs_=abs_)
    ):
        raise AssertionError(
            f"Expected {actual} >= approx({expected}) (rel={rel:.1e}, abs={abs_:.1e}), but it was not."
        )
    return True


def approx_le(actual, expected, *, rel=TOL_GEOMETRY_REL, abs_=TOL_GEOMETRY_ABS):
    """Assert actual is approximately less than or equal to expected."""
    if not (
        _approx_compare(actual, expected, operator.lt, rel=rel, abs_=abs_, allow_approx_eq=False)
        or _approx_compare(actual, expected, operator.eq, rel=rel, abs_=abs_)
    ):
        raise AssertionError(
            f"Expected {actual} <= approx({expected}) (rel={rel:.1e}, abs={abs_:.1e}), but it was not."
        )
    return True
