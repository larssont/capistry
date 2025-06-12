from functools import partial

import pytest
from build123d import Box, Cylinder, Part
from hypothesis import example, given

from capistry.fillet import FilletError, fillet_safe

from .util import strategy as st

dim = st.floats(50, 100)


@example(Cylinder(1, 1), 2, True).xfail(raises=FilletError)
@example(Box(10, 10, 10), 100, True).xfail(raises=FilletError)
@given(
    st.one_of(
        st.builds(Cylinder, dim, dim),
        st.builds(Box, dim, dim, dim),
    ),
    st.floats(min_value=-10, max_value=10),
    st.booleans(),
)
def test_fillet_safe(part: Part, radius: float, fail: bool):
    fillet_safe(part.edges(), radius)


@given(
    st.one_of(
        st.builds(Cylinder, dim, dim),
        st.builds(Box, dim, dim, dim),
    ),
    st.floats(min_value=100, max_value=1000),
    st.booleans(),
)
def test_fillet_safe_fail(part: Part, radius: float, fail: bool):
    call = partial(fillet_safe, part.edges(), radius, fail)

    if fail:
        with pytest.raises(FilletError):
            call()
    else:
        call()
