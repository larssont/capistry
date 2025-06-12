"""
Deformable 2D surface modeling with Bezier surface generation.

This module provides the Surface class for creating and manipulating deformable
2D surfaces defined by offset height grids and optional weight matrices. The
surfaces can be transformed through scaling, tilting, rotation, and mirroring
operations, then converted to Build123D Face objects for 3D modeling applications.

Classes
-------
Surface
    A deformable 2D surface with offset heights and transformation methods.

Functions
---------
_matrix_2x2
    Validator function for 2D numeric matrices with minimum size constraints.
"""

import logging
from numbers import Number
from typing import Any, Self

from attrs import Attribute, define, field
from attrs.validators import *
from build123d import Face, Vector, Vertex
from more_itertools import all_equal, collapse, flatten

from capistry.compare import Comparable, Metric, MetricGroup, MetricLayout
from capistry.utils import mirror_matrix, rotate_matrix

logger = logging.getLogger(__name__)


def _matrix_2x2(_: Any, attribute: Attribute, value: Any) -> None:
    """
    Validate that value is a 2D numeric matrix with minimum dimensions.

    Ensures the input is a properly formatted 2D list of numbers suitable
    for use as offset or weight matrices. Validates structure, dimensions,
    and data types to prevent runtime errors in surface operations.

    Parameters
    ----------
    _ : Any
        Unused instance parameter (attrs validator signature requirement).
    attribute : Attribute
        The attrs attribute being validated (provides name for error messages).
    value : Any
        The value to validate as a 2D numeric matrix.

    Raises
    ------
    TypeError
        If value is not a list, contains non-list rows, or has non-numeric elements.
    ValueError
        If matrix has fewer than 2 rows, unequal row lengths, or fewer than 2 columns.

    Examples
    --------
    Valid 2x2 matrix:
    >>> _matrix_2x2(None, attr, [[1.0, 2.0], [3.0, 4.0]])  # No exception

    Invalid dimensions:
    >>> _matrix_2x2(None, attr, [[1.0]])  # Raises ValueError
    """
    if not isinstance(value, list):
        raise TypeError(f"'{attribute.name}' must be a list (got {type(value).__name__})")

    if len(value) < 2:
        raise ValueError(f"'{attribute.name}' must have at least 2 rows (got {len(value)})")

    if not all(isinstance(row, list) for row in value):
        raise TypeError(f"All rows in '{attribute.name}' must be lists")

    row_lengths = [len(row) for row in value]
    if not all_equal(row_lengths):
        raise ValueError(f"All rows in '{attribute.name}' must be the same length")

    if row_lengths[0] < 2:
        raise ValueError(f"Each row in '{attribute.name}' must have at least 2 columns")

    if not all(
        (isinstance(item, (int, float)) and not isinstance(item, bool))
        for row in value
        for item in row
    ):
        raise TypeError(f"All elements in '{attribute.name}' must be int or float")


@define
class Surface(Comparable):
    """
    A deformable 3D surface defined by offset heights and optional weights.

    Represents a parametric surface that can be deformed by height offsets at
    grid points and influenced by optional weight values. The surface supports
    various transformation operations and can be converted to Build123D Face
    objects.

    Parameters
    ----------
    offsets : list[list[float | int]]
        2D matrix of height offset values. Must be at least 2x2 with uniform
        row lengths. These values define the surface deformation at grid points.
    weights : list[list[float | int]] or None, optional
        Optional 2D matrix of weight values with same dimensions as offsets.
        Controls the influence of each control point in Bezier surface generation.
        Non-positive weights are automatically adjusted, by default None.

    Examples
    --------
    Create a simple 2x2 surface:
    >>> surface = Surface([[0.0, 1.0], [2.0, 3.0]])
    >>> print(surface)
    Surface (2x2)

    Create surface with weights:
    >>> surface = Surface([[0, 1], [2, 3]], weights=[[1.0, 1.5], [1.2, 1.0]])

    Notes
    -----
    The Surface class automatically adjusts weights if any are non-positive
    to preserve relative influence during Bezier surface generation. All
    transformation methods return new instances without modifying the original.
    """

    offsets: list[list[float | int]] = field(validator=_matrix_2x2)
    weights: list[list[float | int]] | None = field(default=None, validator=optional(_matrix_2x2))

    @weights.validator
    def _validate_weights(self, attribute: Attribute, value: list[list[float | int]] | None):
        """Ensure weights matrix matches offsets dimensions."""
        if value is None:
            return

        expected_shape = (len(self.offsets), len(self.offsets[0]))
        actual_shape = (len(value), len(value[0]))

        if actual_shape != expected_shape:
            raise ValueError(
                f"{type(self).__name__} '{attribute.name}' must have the same shape as 'offsets' "
                f"({expected_shape[0]}x{expected_shape[1]}), "
                f"but got {actual_shape[0]}x{actual_shape[1]} instead."
            )

    def __attrs_post_init__(self):
        """Initialize surface and adjust weights if necessary."""
        self._adjust_weights()

    def _adjust_weights(self):
        """Shift weights if any are non-positive to preserve relative influence."""
        if self.weights is None:
            return

        flat_weights = list(flatten(self.weights))
        min_weight = min(flat_weights)

        if min_weight < 1:
            shift = 1 - min_weight
            logger.warning(
                f"Non-positive weights detected (min = {min_weight}); "
                f"shifting all weights by +{shift} to preserve relative influence."
            )
            self.weights = [[w + shift for w in row] for row in self.weights]

    @classmethod
    def flat(cls, rows: int = 3, cols: int = 3) -> "Surface":
        """
        Create a flat surface with all offsets set to zero.

        Generates a Surface instance with uniform zero offsets, representing
        a flat, undeformed surface. Useful as a starting point for surface
        modifications or as a reference baseline.

        Parameters
        ----------
        rows : int, default=3
            Number of rows in the offset matrix
        cols : int, default=3
            Number of columns in the offset matrix

        Returns
        -------
        Surface
            A new Surface instance with all offsets set to 0.0.

        Examples
        --------
        Create default 3x3 flat surface:
        >>> flat_surface = Surface.flat()
        >>> print(flat_surface)
        Surface (3x3)

        Create custom size flat surface:
        >>> large_flat = Surface.flat(rows=5, cols=4)
        >>> print(large_flat)
        Surface (5x4)
        """
        logger.debug("Creating flat %s", cls.__name__, extra={"rows": rows, "cols": cols})
        return cls([[0.0] * cols for _ in range(rows)])

    def scaled(self, offset_factor: float = 1.0) -> "Surface":
        """
        Return a new surface with all offsets scaled by the given factor.

        Multiplies all offset values by the scaling factor while preserving
        the weights unchanged. This is useful for amplifying or reducing
        surface deformations proportionally.

        Parameters
        ----------
        offset_factor : float, default=1.0
            Factor to multiply all offset values by.
            Values > 1.0 amplify deformations, values < 1.0 reduce them.

        Returns
        -------
        Surface
            A new Surface instance with scaled offsets and original weights.

        Examples
        --------
        Double the surface deformation:
        >>> surface = Surface([[0, 1], [2, 3]])
        >>> scaled = surface.scaled(2.0)
        >>> scaled.offsets
        [[0.0, 2.0], [4.0, 6.0]]

        Reduce deformation by half:
        >>> reduced = surface.scaled(0.5)
        >>> reduced.offsets
        [[0.0, 0.5], [1.0, 1.5]]
        """
        logger.debug("Scaling %s", self.__class__.__name__, extra={"factor": offset_factor})
        new_offsets = [[z * offset_factor for z in row] for row in self.offsets]
        return Surface(new_offsets, self.weights)

    def tilted(
        self, amount: float, horizontally: bool = False, ascending: bool = True
    ) -> "Surface":
        """
        Tilt the surface by adding a linear gradient to the offsets.

        Applies a linear height gradient across the surface in either horizontal
        or vertical direction. The gradient creates a planar tilt effect that
        can simulate sloped surfaces.

        Parameters
        ----------
        amount : float
            The maximum vertical offset change across the tilt axis.
        horizontally : bool, default=False
            If True, tilt from left to right. If False, tilt from top to bottom.
        ascending : bool, default=True
            If True, tilt upward in the direction of travel. If False, tilt
            downward.

        Returns
        -------
        Surface
            A new Surface instance with the linear tilt applied to offsets.

        Examples
        --------
        Tilt vertically upward by 2 units:
        >>> surface = Surface([[0, 0], [0, 0]])
        >>> tilted = surface.tilted(2.0, horizontally=False, ascending=True)

        Tilt horizontally downward:
        >>> tilted = surface.tilted(1.5, horizontally=True, ascending=False)
        """
        logger.debug(
            "Tilting %s",
            type(self).__name__,
            extra={"amount": amount, "horizontal": horizontally, "ascending": ascending},
        )

        rows, cols = len(self.offsets), len(self.offsets[0])

        def tilt_factor(i: int, j: int) -> float:
            """Calculate the tilt factor for position (i, j)."""
            if horizontally:
                return (cols - j - 1) if ascending else j
            return (rows - i - 1) if ascending else i

        new_offsets = []
        for i, row in enumerate(self.offsets):
            new_row = []
            for j, offset in enumerate(row):
                new_row.append(offset + amount * tilt_factor(i, j))
            new_offsets.append(new_row)

        return Surface(new_offsets, self.weights)

    def normalized(self, minimum: float = 0.0) -> "Surface":
        """
        Shift the surface so the minimum offset matches the specified value.

        Applies a uniform vertical translation to all offsets so that the
        lowest point on the surface equals the target minimum value. This
        is useful for establishing consistent baseline heights or ensuring
        non-negative offsets.

        Parameters
        ----------
        minimum : float, default=0.0
            The desired value for the minimum offset after normalization.

        Returns
        -------
        Surface
            A new Surface instance with normalized offsets.

        Examples
        --------
        Normalize to zero baseline:
        >>> surface = Surface([[-2, -1], [0, 1]])
        >>> normalized = surface.normalized(0.0)
        >>> normalized.offsets
        [[0.0, 1.0], [2.0, 3.0]]

        Set minimum to specific value:
        >>> normalized = surface.normalized(5.0)
        >>> min(flatten(normalized.offsets))
        5.0
        """
        current_min = min(v for row in self.offsets for v in row)
        shift = minimum - current_min
        logger.debug(
            "Normalizing %s",
            type(self).__name__,
            extra={"minimum": minimum, "shift": shift},
        )
        new_offsets = [[v + shift for v in row] for row in self.offsets]
        return Surface(new_offsets, self.weights)

    def rotated(self, turns: int) -> "Surface":
        """
        Rotate the surface clockwise by 90° increments.

        Rotates both the offset matrix and weights matrix (if present) by
        the specified number of 90-degree clockwise turns. This preserves
        the surface shape while changing its orientation.

        Parameters
        ----------
        turns : int
            Number of 90° clockwise rotations. Values are taken modulo 4,
            so turns=5 is equivalent to turns=1.

        Returns
        -------
        Surface
            A new Surface instance with rotated offsets and weights.

        Examples
        --------
        Rotate 90 degrees clockwise:
        >>> surface = Surface([[1, 2], [3, 4]])
        >>> rotated = surface.rotated(1)

        Rotate 180 degrees:
        >>> rotated = surface.rotated(2)
        """
        turns = turns % 4
        logger.debug(
            "Rotating %s",
            type(self).__name__,
            extra={"turns": turns},
        )

        offsets = rotate_matrix(self.offsets, turns)
        weights = self.weights
        if weights is not None:
            weights = rotate_matrix(weights, n=turns)

        return Surface(offsets=offsets, weights=weights)

    def mirrored(self, horizontal: bool = True, include_weights: bool = True) -> "Surface":
        """
        Mirror the surface across the vertical or horizontal axis.

        Creates a mirror image of the surface by reversing the order of
        elements along the specified axis. Can optionally preserve original
        weights while mirroring only the offsets.

        Parameters
        ----------
        horizontal : bool, default=True
            If True, mirror left-to-right. If False, mirror top-to-bottom.
        include_weights : bool, default=True
            If True, mirror both offsets and weights. If False, only mirror
            offsets while preserving original weights.

        Returns
        -------
        Surface
            A new Surface instance with mirrored data.

        Examples
        --------
        Mirror horizontally (left-right):
        >>> surface = Surface([[1, 2], [3, 4]])
        >>> mirrored = surface.mirrored(horizontal=True)

        Mirror vertically, preserve weights:
        >>> mirrored = surface.mirrored(horizontal=False, include_weights=False)
        """
        logger.debug(
            "Mirroring %s",
            type(self).__name__,
            extra={"vertical": horizontal, "include_weights": include_weights},
        )

        offsets = mirror_matrix(self.offsets, horizontal)
        weights = self.weights
        if include_weights and weights is not None:
            weights = mirror_matrix(weights, horizontal)

        return Surface(offsets, weights if include_weights else self.weights)

    def form_face(self, face: Face) -> Face:
        """
        Create a Bezier surface Face by deforming the input Face  with offset control points.

        Generates a Build123D Face object by interpolating between the vertices of the
        provided face and applying the surface offsets as control point deformations to
        form a bezier surface.

        Parameters
        ----------
        face | Face
            A Build123D Face object with exactly 4 corner vertices that define the
            surface boundaries.

        Returns
        -------
        Face
            A Build123D Face representing the Bezier surface.

        Raises
        ------
        ValueError
            If the input Face does not have exactly four vertices.

        Examples
        --------
        Form face from a rectangle:
        >>
        >>> rectangle = Rectangle(10, 10)
        >>> face = rectangle.faces()[0]
        >>> surface = Surface([[0, 1], [2, 3]])
        >>> bezier_face = surface.form_face(face)

        Notes
        -----
        The vertices are automatically sorted by Y-coordinate (top to bottom)
        then by X-coordinate (left to right) to ensure consistent orientation.
        """
        vertices = face.vertices()
        if len(vertices) != 4:
            raise ValueError(
                f"Expected exactly 4 vertices to define the surface corners, "
                f"but received {len(vertices)}."
            )

        logger.debug(
            "Creating bezier surface from %s",
            self.__class__.__name__,
            extra={"rows": len(self.offsets), "cols": len(self.offsets[0])},
        )

        tl, tr, br, bl = [Vector(c) for c in self._sort_corners(vertices)]
        m, n = len(self.offsets), len(self.offsets[0])
        us = [j / (n - 1) for j in range(n)]
        vs = [i / (m - 1) for i in range(m)]
        ctrl = [
            [
                (
                    tl * (1 - u) * (1 - v)
                    + tr * u * (1 - v)
                    + bl * (1 - u) * v
                    + br * u * v
                    + Vector(0, 0, self.offsets[i][j])
                )
                for j, u in enumerate(us)
            ]
            for i, v in enumerate(vs)
        ]

        face = Face.make_bezier_surface(points=ctrl, weights=self.weights)

        logger.debug(
            "Successfully created bezier surface",
            extra={"control_points": m * n},
        )

        return face

    def _sort_corners(self, vertices: list[Vertex]) -> list[Vertex]:
        """
        Sort corner vertices into consistent order.

        Arranges vertices in the order required for Bezier surface creation:
        [top_left, top_right, bottom_right, bottom_left] based on their
        Y and X coordinates.

        Parameters
        ----------
        vertices : list[Vertex]
            List of exactly 4 vertices to sort.

        Returns
        -------
        list[Vertex]
            Vertices sorted as [top_left, top_right, bottom_right, bottom_left].

        Raises
        ------
        ValueError
            If the number of vertices is not exactly 4.
        """
        if len(vertices) != 4:
            raise ValueError(f"Expected exactly 4 vertices to sort, but received {len(vertices)}.")
        by_y = sorted(vertices, key=lambda v: v.Y, reverse=True)
        top, bottom = by_y[:2], by_y[2:]
        tl, tr = sorted(top, key=lambda v: v.X)
        bl, br = sorted(bottom, key=lambda v: v.X)
        return [tl, tr, br, bl]

    def __str__(self) -> str:
        """Return a string representation showing surface dimensions."""
        return f"{type(self).__name__} ({len(self.offsets)}x{len(self.offsets[0])})"

    @property
    def metrics(self) -> MetricLayout[Self]:
        """
        Expose surface offset and weight extrema through the `capistry.Comparable` system.

        Provides access to minimum and maximum values for both offsets and
        weights.

        Returns
        -------
        MetricLayout
            A metric layout containing a single "Surface" group with the following metrics:
            - Offset - Max: The largest numeric offset value found in the 'offsets' list.
            - Offset - Min: The smallest numeric offset value found in the 'offsets' list.
            - Weights - Max: The largest numeric weight value found in the 'weights' list.
            - Weights - Min: The smallest numeric weight value found in the 'weights' list.

        Notes
        -----
        The metrics use "mm" units for display purposes. Weight metrics
        return empty strings if no weights are defined.
        """
        return MetricLayout(
            owner=self,
            groups=(
                MetricGroup(
                    "Surface",
                    (
                        Metric(
                            "Offset - Max",
                            lambda: max(collapse(self.offsets, base_type=Number), default=""),
                            "mm",
                        ),
                        Metric(
                            "Offset - Min",
                            lambda: min(collapse(self.offsets, base_type=Number), default=""),
                            "mm",
                        ),
                        Metric(
                            "Weights - Max",
                            lambda: max(collapse(self.weights, base_type=Number), default=""),
                            "mm",
                        ),
                        Metric(
                            "Weights - Min",
                            lambda: min(collapse(self.weights, base_type=Number), default=""),
                            "mm",
                        ),
                    ),
                ),
            ),
        )
