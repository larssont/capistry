"""
Module for generating 3D sprue geometries used to connect caps in a panel layout.

Sprues are used to physically link caps in a grid to ensure minimum size requirements
are met during manufacturing. These are created as build123d solids and inserted
between adjacent caps in rows or columns.

Sprue types are intended to be passed into the `Panel` class to control how connections
are formed between items.

Classes
-------
Sprue : Abstract base class defining the interface for all sprue types.
SpruePolygon : Sprue with a regular polygon cross-section.
SprueCylinder : Sprue with a circular (cylindrical) cross-section.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from build123d import (
    Align,
    Cylinder,
    IntersectingLine,
    Part,
    Plane,
    RegularPolygon,
    Vector,
    extrude,
)

from .cap import Cap

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Sprue(ABC):
    """
    Abstract base class for a sprue element used to connect caps.

    Parameters
    ----------
    diameter : float, default=1.5
        Diameter of the sprue cross-section.
    inset : float or None, default=None
        Optional distance that the sprue extends into the cap.
        If None, a default inset of 2 units is used.

    Attributes
    ----------
    diameter : float
        Diameter in mm of the sprue cross-section.
    inset : float or None
        Custom inset value in mm or None.
    """

    diameter: float = 1.5
    inset: float | None = None

    def _get_inset(self, cap: Cap) -> float:
        """
        Compute how far the sprue should extend into the cap.

        Parameters
        ----------
        cap : Cap
            The cap to calculate inset for.

        Returns
        -------
        float
            Effective inset distance.
        """
        return cap.wall + (self.inset if self.inset is not None else cap.wall)

    @abstractmethod
    def _create(self, length: float) -> Part:
        """
        Create a sprue segment of given length.

        Parameters
        ----------
        length : float
            Length of the sprue segment.

        Returns
        -------
        Part
            The constructed 3D sprue part.
        """

    def _between(self, start: Vector, end: Vector) -> Part:
        """
        Generate a sprue segment between two points.

        Parameters
        ----------
        start : Vector
            Starting point of the sprue.
        end : Vector
            Ending point of the sprue.

        Returns
        -------
        Part
            The 3D sprue geometry between the two points.

        Raises
        ------
        ValueError
            If the points are too close or aligned with the Z axis.
        TypeError
            If the result is not a valid build123d Part.
        """
        logger.debug(
            "Creating sprue segment",
            extra={
                "start": start.to_tuple(),
                "end": end.to_tuple(),
                "length": (end - start).length,
            },
        )
        x_dir = end - start
        if x_dir.length < 1e-4:
            raise ValueError(
                f"Sprue segment too short: distance between "
                f"start {start} and end {end} is nearly zero."
            )

        if x_dir.cross(Vector(0, 0, 1)).length < 1e-4:
            raise ValueError(
                f"Invalid direction: start {start} and end {end} vectors "
                f"are parallel to the Z axis, which is not allowed."
            )

        p = self._create(x_dir.length)
        p.label = str(self)

        res = Plane(origin=start, x_dir=x_dir) * p

        if not isinstance(res, Part):
            raise TypeError(f"Expected Shape from Plane * Shape, got {type(res)}")

        return res

    def connect_horizontally(self, c1: Cap, c2: Cap) -> Part:
        """
        Connect two caps using a horizontal sprue.

        Parameters
        ----------
        c1 : Cap
            Left cap.
        c2 : Cap
            Right cap.

        Returns
        -------
        Part
            The connecting sprue part.
        """
        y_max = min(c1.right.bounding_box().max.Y, c2.left.bounding_box().max.Y)
        y_min = max(c1.right.bounding_box().min.Y, c2.left.bounding_box().min.Y)

        v = c1.right @ 0.5
        v.Y = (y_max + y_min) / 2

        l1 = IntersectingLine(start=v, direction=Vector(1), other=c2.left)
        l2 = IntersectingLine(start=l1 @ 1, direction=Vector(-1), other=c1.right)

        return self._between(l2 @ 0 + (self._get_inset(c1), 0), l2 @ 1 - (self._get_inset(c2), 0))

    def connect_vertically(self, c1: Cap, c2: Cap) -> Part:
        """
        Connect two caps using a vertical sprue.

        Parameters
        ----------
        c1 : Cap
            Top cap.
        c2 : Cap
            Bottom cap.

        Returns
        -------
        Part
            The connecting sprue part.
        """
        x_max = min(c1.bottom.bounding_box().max.X, c2.top.bounding_box().max.X)
        x_min = max(c1.bottom.bounding_box().min.X, c2.top.bounding_box().min.X)

        v = c1.bottom @ 0.5
        v.X = (x_max + x_min) / 2

        l1 = IntersectingLine(start=v, direction=Vector(0, -1), other=c2.top)
        l2 = IntersectingLine(start=l1 @ 1, direction=Vector(0, 1), other=c1.bottom)

        return self._between(l2 @ 0 - (0, self._get_inset(c1)), l2 @ 1 + (0, self._get_inset(c2)))

    def __str__(self):
        return f"{type(self).__name__} (Ø{self.diameter})"


@dataclass(frozen=True)
class SpruePolygon(Sprue):
    """
    Sprue with a polygonal cross-section.

    Parameters
    ----------
    diameter : float, default=1.5
        Diameter of the circumscribed circle around the polygon.
    inset : float or None, default=None
        Optional inset in mm into the cap.
    sides : int, default=4
        Number of sides in the polygon.
    """

    sides: int = 4

    def _create(self, length: float) -> Part:
        """
        Create a polygonal sprue segment of the specified length.

        Parameters
        ----------
        length : float
            Length of the sprue segment.

        Returns
        -------
        Part
            The polygonal 3D sprue geometry.

        Raises
        ------
        TypeError
            If extrusion did not result in a valid Part.
        """
        logger.debug("Creating polygon sprue", extra={"sides": self.sides, "length": length})
        poly = RegularPolygon(
            radius=self.diameter / 2,
            side_count=self.sides,
            rotation=90 - 180 / self.sides,
            major_radius=False,
            align=(Align.CENTER, Align.MAX),
        )
        res = Plane.YZ * extrude(to_extrude=poly, amount=length)
        if not isinstance(res, Part):
            raise TypeError(f"Expected Shape from Plane * Shape, got {type(res)}")
        return res


@dataclass(frozen=True)
class SprueCylinder(Sprue):
    """
    Sprue with a circular (cylindrical) cross-section.

    Parameters
    ----------
    diameter : float, default=1.5
        Diameter of the cylindrical sprue.
    inset : float or None, default=None
        Optional inset in mm into the cap.
    """

    def _create(self, length: float) -> Part:
        """
        Create a cylindrical sprue segment of the specified length.

        Parameters
        ----------
        length : float
            Length of the sprue segment.

        Returns
        -------
        Part
            The cylindrical 3D sprue geometry.

        Raises
        ------
        TypeError
            If extrusion did not result in a valid Part.
        """
        logger.debug("Creating cylindrical sprue", extra={"length": length})
        res = Plane.YZ * Cylinder(
            radius=self.diameter / 2,
            height=length,
            align=(Align.CENTER, Align.MAX, Align.MIN),
        )
        if not isinstance(res, Part):
            raise TypeError(f"Expected Part from Plane * Shape, got {type(res)}")
        return res
