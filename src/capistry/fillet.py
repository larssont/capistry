"""
Fillet strategies for keycaps.

This module provides various fillet strategies for applying rounded edges to
keyboard caps including MXStem, ChocStem, and other Cap-type classes. The strategies
allow for customizable filleting of outer edges, inner edges, and skirt areas.

Classes
-------
FilletStrategy : ABC
    Abstract base class for all fillet strategies.
FilletUniform : FilletStrategy
    Applies uniform outer fillets to all edges.
FilletWidthDepth : FilletStrategy
    Applies differentiated fillets left-to-right, then front-to-back.
FilletDepthWidth : FilletStrategy
    Applies differentiated fillets front-to-back, then left-to-right.
FilletMiddleTop : FilletStrategy
    Applies differentiated fillets to mid-height edges, then top perimeter.

Functions
---------
fillet_safe : function
    Safely applies fillets with error handling and logging.

Exceptions
----------
FilletError : Exception
    Raised when fillet operations fail unexpectedly.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, fields
from typing import Self

from build123d import (
    Axis,
    BuildPart,
    ChamferFilletType,
    Curve,
    Face,
    Part,
    Select,
    ShapeList,
    Sketch,
    fillet,
)

from capistry.compare import Comparable, Metric, MetricGroup, MetricLayout

logger = logging.getLogger(__name__)


class FilletError(Exception):
    """
    Exception raised when a fillet operation fails.

    This exception is raised when attempting and the operation cannot be completed
    due to geometric constraints.

    Parameters
    ----------
    radius : float
        The fillet radius that caused the failure.
    part : str
        The name/type of the object that failed to fillet.
    cause : Exception, default=None
        The underlying exception that triggered this error.

    Attributes
    ----------
    radius : float
        The fillet radius that caused the failure.
    part : str
        The name/type of the object that failed to fillet.
    """

    def __init__(self, radius: float, part: str, cause: Exception | None = None):
        self.radius = radius
        self.part = part
        super().__init__(f"Fillet failed with radius={radius} on {part}")
        self.__cause__ = cause


def fillet_safe(
    objects: ChamferFilletType | Iterable[ChamferFilletType],
    radius: float,
    threshold: float = 1e-6,
    err: bool = True,
) -> Sketch | Part | Curve | None:
    """
    Safely apply a fillet to objects with error handling.

    Attempts to apply a fillet operation to the specified `ChamferFilletType`s (i.e. edges).
    Only applies the fillet if it is above the threshold.

    Parameters
    ----------
    objects : ChamferFilletType or Iterable[ChamferFilletType]
        The Build123d objects (edges, faces) to fillet.
    radius : float
        The fillet radius in millimeters.
    threshold : float, default=1e-6
        The minimum radius required to attempt a fillet operation.
        Values less than or equal to this will skip the operation.
    err : bool, default=True
        Whether to raise FilletError on failure. If False, returns None on failure.

    Returns
    -------
    Sketch, Part, Curve, or None
        The filleted object on success, or None if radius is too small or
        operation fails with err=False.

    Raises
    ------
    FilletError
        When fillet operation fails and err=True.
    """
    if radius > threshold:
        try:
            return fillet(objects=objects, radius=radius)
        except Exception as e:
            logger.exception(
                "Failed to apply fillet",
                extra={
                    "radius": radius,
                    "object_type": type(objects).__name__,
                },
                exc_info=e,
            )
            if err:
                raise FilletError(radius, type(objects).__name__, e) from e
    else:
        logger.debug(
            "Radius %.6f is below threshold %.6f — skipping fillet",
            radius,
            threshold,
        )

    return None


@dataclass
class FilletStrategy(Comparable, ABC):
    """
    Abstract base class for `capistry.Cap` fillet strategies.

    Defines the interface for applying various types of fillets to caps
    such as `capistry.TrapezoidCap`, `capistry.RectangularCap`, or any other `capistry.Cap`
    subclasses. Provides common parameters and methods for inner and skirt filleting
    while leaving outer fillet implementation to concrete subclasses.

    Parameters
    ----------
    skirt : float, default=0.25
        Radius in mm for skirt fillets applied to the bottom-most face edges.
        Creates a subtle rounded transition on the bottom wall edges.
    inner : float, default=1.0
        Radius in mm for inner fillets applied to Z-axis edges at the last step.
        Smooths internal corners within the keycap shell.

    Methods
    -------
    apply_outer(p)
        Apply outer fillets to the cap (must be implemented by subclasses).
    apply_inner(p)
        Apply inner fillets to Z-axis edges.
    apply_skirt(p)
        Apply skirt fillet to bottom face edges.
    metrics
        Returns MetricLayout describing the strategy's parameters.

    Notes
    -----
    This class is designed specifically for cap filleting and expects
    BuildPart objects that represent `capistry.Cap` shapes.
    Fillet operations are only meant to be called from `capistry.Cap.compound`.
    """

    skirt: float = 0.25
    inner: float = 1

    @abstractmethod
    def apply_outer(self, p: BuildPart):
        """
        Apply outer fillets to the `capistry.Cap`.

        This method must be implemented by concrete subclasses to define how
        outside edges fillets are applied.

        Parameters
        ----------
        p : BuildPart
            The BuildPart representing a Cap instance (MXStem, choc, etc.) to
            which outer fillets should be applied.

        Notes
        -----
        Implementations should use fillet_safe() for robust error handling and
        should take into consideration the different geometries of different caps.
        """
        pass

    def apply_inner(self, p: BuildPart):
        """
        Apply inner fillets to Z-axis edges of the keyboard cap.

        Applies fillets to internal edges along the Z-axis, typically smoothing
        the inner cavity.

        Parameters
        ----------
        p : BuildPart
            The BuildPart representing a Cap to
            which inner fillets should be applied.
        """
        logger.debug("Applying inner fillet", extra={"radius": self.inner})
        fillet_safe(p.edges(Select.LAST).group_by(Axis.Z)[1:], self.inner)

    def apply_skirt(self, p: BuildPart):
        """
        Apply skirt fillet to the bottom face edges of the keycap.

        Creates a subtle rounded transition at the bottom edge of the keycap's walls.
        Improves aesthetics and reduces stress concentrations during 3D-printing.

        Parameters
        ----------
        p : BuildPart
            The BuildPart representing a Cap instance (MXStem, choc, etc.) to
            which the skirt fillet should be applied.
        """
        logger.debug("Applying skirt fillet", extra={"radius": self.skirt})
        fillet_safe(p.faces(Select.LAST).sort_by()[0].edges(), self.skirt)

    @property
    def metrics(self) -> MetricLayout[Self]:
        """
        Expose all numeric parameters of this strategy through the `capistry.Comparable` system.

        Automatically discovers all numeric fields (int, float) that don't start
        with underscore and creates corresponding Metric objects with proper
        formatting and units.

        Returns
        -------
        MetricLayout
            A MetricLayout containing all numeric fields organized under a
            "Fillet" group, with units in millimeters and human-readable names.
        """
        numerics = [
            f.name
            for f in fields(self)
            if not f.name.startswith("_") and isinstance(getattr(self, f.name), int | float)
        ]

        return MetricLayout(
            owner=self,
            groups=(
                MetricGroup(
                    "Fillet",
                    tuple(
                        Metric(
                            name.replace("_", " ").title(),
                            lambda n=name: getattr(self, n),
                            unit="mm",
                        )
                        for name in numerics
                    ),
                ),
            ),
        )

    def __str__(self) -> str:
        """Return the class name as the string representation."""
        return type(self).__name__


@dataclass
class FilletUniform(FilletStrategy):
    """
    Uniform outer fillet strategy for `capistry.Cap`.

    Applies the same fillet radius to all outer edges of keyboard caps,
    creating a consistent, symmetrical appearance.

    Parameters
    ----------
    outer : float, default=1.5
        Radius in mm for outer fillets applied to all Z-axis edge groups
        (excluding the bottom-most group). Creates uniform rounding on all
        main visible edges of the keycap.
    skirt : float, default=0.25
        Inherited from FilletStrategy. Radius for bottom face edge fillets.
    inner : float, default=1.0
        Inherited from FilletStrategy. Radius for internal Z-axis edge fillets.
    """

    outer: float = 1.5
    """Fillet radius for outer edges."""

    def apply_outer(self, p: BuildPart):
        """
        Apply uniform outer fillets to all Z-axis edge groups, excluding the bottom-most group.

        Parameters
        ----------
        p : BuildPart
            The BuildPart representing a `capistry.Cap` instance to
            which uniform outer fillets should be applied.
        """
        logger.debug("Applying outer fillets (uniform)", extra={"radius": self.outer})
        fillet_safe(p.edges().group_by(Axis.Z)[1:], self.outer)


@dataclass
class FilletWidthDepth(FilletStrategy):
    """
    Directional fillet strategy applying width edges (left/right) before depth edges (front/back).

    Parameters
    ----------
    front : float, default=3.0
        Radius in mm for front edge fillets (negative Y direction).
    back : float, default=2.0
        Radius in mm for back edge fillets (positive Y direction).
    left : float, default=1.0
        Radius in mm for left side fillets (negative X direction).
    right : float, default=1.0
        Radius in mm for right side fillets (positive X direction).
    skirt : float, default=0.25
        Inherited from FilletStrategy. Radius for bottom face edge fillets.
    inner : float, default=1.0
        Inherited from FilletStrategy. Radius for internal Z-axis edge fillets.
    """

    front: float = 3
    back: float = 2
    left: float = 1
    right: float = 1

    def apply_outer(self, p: BuildPart):
        """
        Apply outer fillet radii with (left/right) processed first.

        Parameters
        ----------
        p : BuildPart
            The BuildPart representing a `capistry.Cap` instance to
            which outer fillets should be applied.
        """
        logger.debug(
            "Applying outer fillets (sides-first)",
            extra={
                "front": self.front,
                "back": self.back,
                "left": self.left,
                "right": self.right,
            },
        )

        fillet_safe(p.faces().sort_by(Axis.Z)[-1].edges().sort_by(Axis.Y)[0], self.front)
        fillet_safe(p.faces().sort_by(Axis.Z)[-1].edges().sort_by(Axis.Y)[-1], self.back)
        fillet_safe(p.faces().sort_by(Axis.X)[-1].edges().sort_by(Axis.Z)[1:], self.left)
        fillet_safe(p.faces().sort_by(Axis.X)[0].edges().sort_by(Axis.Z)[1:], self.right)


@dataclass
class FilletDepthWidth(FilletStrategy):
    """
    Directional fillet strategy applying depth edges (front/back) before width edges (left/right).

    Parameters
    ----------
    front : float, default=2.0
        Radius in mm for front edge fillets (negative Y direction).
    back : float, default=1.0
        Radius in mm for back edge fillets (positive Y direction).
    left : float, default=3.0
        Radius in mm for left side fillets (negative X direction).
    right : float, default=3.0
        Radius in mm for right side fillets (positive X direction).
    skirt : float, default=0.25
        Inherited from FilletStrategy. Radius for bottom face edge fillets.
    inner : float, default 1.0
        Inherited from FilletStrategy. Radius for internal Z-axis edge fillets.
    """

    front: float = 2
    back: float = 1
    left: float = 3
    right: float = 3

    def apply_outer(self, p: BuildPart):
        """
        Apply outer fillet radii with (left/right) processed last.

        Parameters
        ----------
        p : BuildPart
            The BuildPart representing a `capistry.Cap` instance to
            which outer fillets should be applied.
        """
        logger.debug(
            "Applying outer fillets (sides-last)",
            extra={
                "front": self.front,
                "back": self.back,
                "left": self.left,
                "right": self.right,
            },
        )

        fillet_safe(p.faces().sort_by(Axis.Z)[-1].edges().sort_by(Axis.X)[0], self.left)
        fillet_safe(p.faces().sort_by(Axis.Z)[-1].edges().sort_by(Axis.X)[-1], self.right)
        fillet_safe(p.faces().sort_by(Axis.Y)[0].edges().sort_by(Axis.Z)[1:], self.front)
        fillet_safe(p.faces().sort_by(Axis.Y)[-1].edges().sort_by(Axis.Z)[1:], self.back)


@dataclass
class FilletMiddleTop(FilletStrategy):
    """
    Fillet strategy that applies middle-height edges first, then top face edges.

    Parameters
    ----------
    top : float, default=0.75
        Radius for the topmost edge fillets (upper Z direction).
    middle : float, default=2.5
        Radius for edges located in the mid-section of the part.
    skirt : float, default=0.25
        Inherited from FilletStrategy. Radius for bottom face edge fillets.
    inner : float, default=1.0
        Inherited from FilletStrategy. Radius for internal Z-axis edge fillets.
    """

    top: float = 0.75
    middle: float = 2.5

    def apply_outer(self, p: BuildPart):
        """
        Apply mid-section and top edge fillets to the outer geometry.

        First applies fillets to mid-height vertical or slanted edges,
        followed by fillets on the uppermost perimeter.

        Parameters
        ----------
        p : BuildPart
            The BuildPart representing a Cap instance (e.g., MXStem or Choc).
        """
        logger.debug(
            "Applying outer fillets (top-to-middle)",
            extra={"top": self.top, "middle": self.middle},
        )

        def faces() -> ShapeList[Face]:
            # Sort faces by height (Z) and prioritize side faces
            # (i.e., those with normals not closely aligned with Z).
            return (
                p.faces()
                .sort_by(Axis.Z, reverse=True)
                .sort_by(lambda f: abs(f.normal_at().dot(Axis.Z.direction)))
            )

        # Fillet mid-height edges on side faces:
        #   - Exclude top/bottom Z-aligned faces (last two in list).
        #   - Use `% 0.5` to find the edge tangent at midpoint.
        #   - Keep edges with significant vertical (Z) tangent component.
        fillet_safe(
            faces()[:-2].edges().filter_by(lambda e: abs((e % 0.5).Z) > 0.5),  # noqa: PLR2004
            self.middle,
        )

        # Fillet the topmost usable face's edges:
        #   - From last two faces, pick the highest one by Z position.
        fillet_safe(
            faces()[-2:].sort_by(Axis.Z)[-1].edges(),
            self.top,
        )
