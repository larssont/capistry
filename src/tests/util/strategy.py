"""
Reusable Hypothesis strategies for testing.

Provides pre-configured strategies for common data types and objects
used in capistry tests. Defaults suit most cases but are customizable.
"""

import logging
from dataclasses import MISSING, fields
from enum import Enum
from math import pi
from typing import Any, Callable, Type, TypeVar

from build123d import BuildLine, BuildSketch, CenterOf, Circle, Polyline, Vector, Vertex, make_face
from hypothesis import strategies as st
from more_itertools import interleave_longest, repeatfunc
from ocp_vscode import *

from capistry.fillet import FilletError
from capistry.sprue import Sprue, SprueCylinder, SpruePolygon
from capistry.stem import ChocStem, MXStem
from capistry.surface import Surface
from capistry.taper import Taper
from capistry.utils import spaced_points
from tests.util.approximate import MAX_GEOMETRY_VALUE, MIN_GEOMETRY_VALUE

logger = logging.getLogger(__name__)

T = TypeVar("T")


def wrap(x: T) -> st.SearchStrategy[T]:
    """Wrap value in a strategy if not already one."""
    if isinstance(x, st.SearchStrategy):
        return x
    return st.just(x)


def unwrap(
    draw: st.DrawFn, x: T | st.SearchStrategy[T], condition: Callable[[Any], bool] | None = None
) -> T:
    """
    Draw a value from strategy or return value directly.

    Recursively unwraps nested strategies.
    """

    def _draw(
        draw: st.DrawFn, x: T | st.SearchStrategy[T], condition: Callable[[Any], Any] | None = None
    ) -> T:
        if not isinstance(x, st.SearchStrategy):
            return x
        if condition is not None:
            return draw(x.filter(condition))
        return draw(x)

    def fn(item: Any) -> Any:
        match item:
            case list():
                return [fn(v) for v in item]
            case tuple():
                return tuple(fn(v) for v in item)
            case dict():
                return {fn(k): fn(v) for k, v in item.items()}
            case st.SearchStrategy():
                return fn(_draw(draw, item))
            case _:
                return item

    return _draw(draw, fn(x), condition)


def any_except(*exclude: Type):
    """Strategy for any type except given types."""
    return st.from_type(type).flatmap(st.from_type).filter(lambda x: not isinstance(x, exclude))


def sample_near(
    val: int | float, n: int = 3, pct: float = 10.0, include_val: bool = True
) -> st.SearchStrategy:
    """
    Sample values near val by percentage steps.

    Parameters
    ----------
    val : int or float
        Base value.
    n : int, default=3
        Number of steps up/down.
    pct : float, default=10
        Step size percentage.
    include_val : bool, default=True
        Include val itself.

    Returns
    -------
    SearchStrategy
        Strategy with sampled values.
    """

    def offsets(sign: int):
        return [val + sign * val * (pct / 100) * i for i in range(1, n + 1)]

    vals = list(interleave_longest(offsets(1), offsets(-1)))
    if include_val:
        vals.append(val)

    return st.sampled_from(sorted(set(vals)))


def get_field_default(cls, field_name: str) -> Any:
    """Get default value for dataclass field."""
    for f in fields(cls):
        if f.name == field_name:
            if f.default is not MISSING:
                return f.default
            elif f.default_factory is not MISSING:
                return f.default_factory()
            else:
                raise ValueError(f"No default for field '{field_name}'")
    raise AttributeError(f"No field named '{field_name}' in {cls.__name__}")


# -----------------------------------------------------------------------------
# Numeric strategies
# -----------------------------------------------------------------------------


class NumProfile(Enum):
    DEFAULT = "default"
    GEOMETRY = "geometry"

    def bounds(self) -> tuple[float, float]:
        if self is NumProfile.DEFAULT:
            return (-100000, 100000)
        elif self is NumProfile.GEOMETRY:
            return (1e-6, 1000)
        else:
            raise TypeError(f"Unsupported profile {self}")


def ints(
    min_value: int | None = None,
    max_value: int | None = None,
) -> st.SearchStrategy[int]:
    """Generate integers within optional bounds."""
    return st.integers(min_value=min_value, max_value=max_value)


def floats(
    min_value: float | None = None,
    max_value: float | None = None,
    allow_nan: bool = False,
    allow_infinity: bool = False,
    exclude_max: bool = False,
    exclude_min: bool = False,
    profile: NumProfile = NumProfile.DEFAULT,
) -> st.SearchStrategy[float]:
    """Generate floats within optional bounds and profile."""
    profile_min, profile_max = profile.bounds()
    min_value = min_value if min_value is not None else profile_min
    max_value = max_value if max_value is not None else profile_max

    return st.floats(
        min_value=min_value,
        max_value=max_value,
        allow_nan=allow_nan,
        allow_infinity=allow_infinity,
        exclude_max=exclude_max,
        exclude_min=exclude_min,
    )


def angles_degrees(min_value: float = 0.0, max_value: float = 360.0) -> st.SearchStrategy[float]:
    """Generate angles in degrees."""
    return floats(min_value=min_value, max_value=max_value)


def angles_radians(
    min_value: float = 0.0,
    max_value: float = 2 * pi,
) -> st.SearchStrategy[float]:
    """Generate angles in radians."""
    return floats(min_value=min_value, max_value=max_value)


# -----------------------------------------------------------------------------
# Tensor strategy
# -----------------------------------------------------------------------------


@st.composite
def tensors(
    draw,
    value: Any = st.integers(-100, 100),
    shape: tuple[int | st.SearchStrategy[int]] = (
        st.integers(2, 10),
        st.integers(2, 10),
    ),
    dynamic: bool = False,
) -> Any:
    """Generate nested lists with given shape and values."""
    if not isinstance(shape, tuple):
        raise TypeError(f"`shape` must be a tuple, got {type(shape).__name__!r}")

    shape = shape if dynamic else unwrap(draw, shape)

    def build(depth: int) -> Any:
        if depth == len(shape):
            return draw(value)

        size = unwrap(draw, shape)[depth] if dynamic else shape[depth]

        if not isinstance(size, int):
            raise TypeError(
                f"Expected dimension size int at depth {depth}, got {type(size).__name__!r}: {size}"
            )

        return list(repeatfunc(lambda: build(depth + 1), times=size))

    return build(0)


# -----------------------------------------------------------------------------
# Taper strategy
# -----------------------------------------------------------------------------


@st.composite
def tapers(
    draw: st.DrawFn, min_value: float | None = None, max_value: float | None = None
) -> Taper:
    """Generate Taper with optional bounds."""
    strat = floats(min_value=min_value, max_value=max_value)
    return Taper(
        front=draw(strat),
        back=draw(strat),
        left=draw(strat),
        right=draw(strat),
    )


# -----------------------------------------------------------------------------
# Shapes and Points
# -----------------------------------------------------------------------------


@st.composite
def faces(
    draw,
    size: int | float | st.SearchStrategy[int | float] = ints(10, 100),
    vertices: int | st.SearchStrategy[int] = 4,
):
    """Generate polygon face by sampling a circle outline."""
    vertices = unwrap(draw, vertices)
    if vertices < 3:
        raise ValueError("Polygon must have at least 3 sides")

    outline = Circle(unwrap(draw, size)).edges()[0]
    vertices = [outline @ x for x in spaced_points(vertices, tolerance=0.025, rand=draw(randoms()))]

    with BuildSketch() as sk:
        with BuildLine():
            Polyline(*vertices, close=True)
        make_face()

    return sk.sketch.faces()[0]


@st.composite
def vectors(
    draw,
    x: float | st.SearchStrategy[float] = floats(min_value=-100, max_value=100),
    y: float | st.SearchStrategy[float] = floats(min_value=-100, max_value=100),
    z: float | st.SearchStrategy[float] = floats(min_value=-100, max_value=100),
) -> Vector:
    """Generate build123d.Vector with optional coordinates."""
    return Vector(unwrap(draw, x), unwrap(draw, y), unwrap(draw, z))


@st.composite
def vertices(
    draw,
    x: float | None = None,
    y: float | None = None,
    z: float | None = None,
) -> Vertex:
    """Generate build123d.Vertex from vector."""
    return Vertex(draw(vectors(x, y, z)))


# -----------------------------------------------------------------------------
# Sprue strategies
# -----------------------------------------------------------------------------


@st.composite
def sprues_polygon(
    draw: st.DrawFn,
    min_diameter: float = MIN_GEOMETRY_VALUE,
    max_diameter: float = MAX_GEOMETRY_VALUE,
    sides: int | st.SearchStrategy[int] = ints(3, 10),
) -> SpruePolygon:
    """Generate SpruePolygon."""
    return SpruePolygon(
        diameter=draw(floats(min_diameter, max_diameter)),
        inset=draw(st.one_of(st.none(), floats())),
        sides=unwrap(draw, sides),
    )


@st.composite
def sprues_cylinder(
    draw: st.DrawFn,
    min_diameter: float = MIN_GEOMETRY_VALUE,
    max_diameter: float = MAX_GEOMETRY_VALUE,
) -> SprueCylinder:
    """Generate SprueCylinder."""
    return SprueCylinder(
        diameter=draw(floats(min_value=min_diameter, max_value=max_diameter)),
        inset=draw(st.one_of(st.none(), floats())),
    )


@st.composite
def sprues(draw: st.DrawFn) -> Sprue:
    """Generate Sprue (polygon or cylinder)."""
    return draw(st.one_of(sprues_polygon(), sprues_cylinder()))


# -----------------------------------------------------------------------------
# Surface strategy
# -----------------------------------------------------------------------------


@st.composite
def surfaces(
    draw,
    offset: int | float | st.SearchStrategy[int | float] = ints(-100, 100),
    weight: int | float | st.SearchStrategy[int | float] = ints(1, 100),
    rows: int | st.SearchStrategy[int] = ints(2, 10),
    cols: int | st.SearchStrategy[int] = ints(2, 10),
) -> Surface:
    """Generate Surface with offsets and optional weights."""
    rows = unwrap(draw, rows)
    cols = unwrap(draw, cols)

    offsets: list[list[int | float]] = draw(tensors(offset, shape=(rows, cols)))

    weights: list[list[int | float]] = draw(
        st.one_of(
            st.none(),
            tensors(weight, shape=(rows, cols)),
        )
    )
    return Surface(offsets=offsets, weights=weights)


# -----------------------------------------------------------------------------
# Stem strategies
# -----------------------------------------------------------------------------


@st.composite
def stems(draw, fillet: bool = False, fail: bool = True):
    """Generate either MX or Choc stem."""
    return draw(st.one_of(stems_mx(fillet=fillet, fail=fail), stems_choc(fillet=fillet, fail=fail)))


@st.composite
def stems_mx(draw, fillet: bool = False, fail: bool = True):
    """Generate MXStem with optional fillets."""

    def sample(name: str, n: int = 2, pct: float = 10, zero: bool = False):
        strat = sample_near(get_field_default(MXStem, name), n=n, pct=pct)
        if zero:
            strat = st.just(0) | strat
        return draw(strat)

    fillet_stem = sample("fillet_stem", zero=True) if fillet else 0
    fillet_outer = sample("fillet_outer", zero=True) if fillet else 0

    try:
        return MXStem(
            center_at=draw(sampled_from((CenterOf.GEOMETRY, CenterOf.BOUNDING_BOX))),
            cylinder_height=sample("cylinder_height"),
            cylinder_radius=sample("cylinder_radius"),
            cross_length=sample("cross_length"),
            cross_width=sample("cross_width"),
            fillet_stem=fillet_stem,
            fillet_outer=fillet_outer,
        )
    except FilletError:
        if fillet and fail:
            raise


@st.composite
def stems_choc(draw, fillet: bool = False, fail: bool = True):
    """Generate ChocStem with optional fillets."""

    def sample(name: str, n: int = 2, pct: float = 10, zero: bool = False):
        strat = sample_near(get_field_default(ChocStem, name), n=n, pct=pct)
        if zero:
            strat = st.just(0) | strat
        return draw(strat)

    fillet_legs_top = sample("fillet_legs_top", zero=True) if fillet else 0
    fillet_legs_side = sample("fillet_legs_side", zero=True) if fillet else 0
    fillet_legs_bottom = sample("fillet_legs_bottom", zero=True) if fillet else 0

    try:
        return ChocStem(
            center_at=draw(sampled_from((CenterOf.GEOMETRY, CenterOf.BOUNDING_BOX))),
            leg_length=sample("leg_length"),
            leg_width=sample("leg_width"),
            leg_spacing=sample("leg_spacing"),
            leg_height=sample("leg_height"),
            arc_length_ratio=sample("arc_length_ratio"),
            arc_width_ratio=sample("arc_width_ratio"),
            cross_length=sample("cross_length"),
            cross_height=sample("cross_height"),
            cross_width=sample("cross_width"),
            cross_spacing=sample("cross_spacing"),
            fillet_legs_top=fillet_legs_top,
            fillet_legs_side=fillet_legs_side,
            fillet_legs_bottom=fillet_legs_bottom,
            include_cross=draw(booleans()),
            include_arc=draw(booleans()),
        )
    except FilletError:
        if fillet and fail:
            raise


# -----------------------------------------------------------------------------
# Aliases for common Hypothesis strategies
# -----------------------------------------------------------------------------


complex_numbers = st.complex_numbers
binary = st.binary
text = st.text
just = st.just
none = st.none
nothing = st.nothing
booleans = st.booleans
lists = st.lists
tuples = st.tuples
composite = st.composite
randoms = st.randoms
data = st.data
DataObject = st.DataObject
recursive = st.recursive
shared = st.shared
one_of = st.one_of
sampled_from = st.sampled_from
builds = st.builds
