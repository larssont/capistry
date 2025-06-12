"""
Keycap Stem Generation Module.

This module provides classes for creating the stem part of keycaps.

Classes
-------
Stem
    Abstract base class for all keycap stem geometries with common functionality.
MXStem
    Cherry MX-compatible keycap stem with cylindrical body and cross-shaped cavity.
ChocStem
    Kailh Choc low-profile keycap stem with dual legs and optional cross support.

Constants
---------
CAP_STEM_JOINT : str
    Joint identifier for connecting stems to keycap bodies.
STEM_CAP_JOINT : str
    Joint identifier for connecting keycap bodies to stems.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import cached_property
from typing import Self

from build123d import (
    Align,
    Axis,
    BuildLine,
    BuildPart,
    BuildSketch,
    CenterOf,
    Circle,
    Compound,
    GridLocations,
    Keep,
    Location,
    Locations,
    Mode,
    Plane,
    Polyline,
    Rectangle,
    RigidJoint,
    SagittaArc,
    Sketch,
    SortBy,
    Vector,
    Vertex,
    extrude,
    make_face,
    mirror,
    offset,
    split,
)

from capistry.compare import Comparable, Metric, MetricGroup, MetricLayout
from capistry.utils import gloc

from .fillet import fillet_safe

logger = logging.getLogger(__name__)

CAP_STEM_JOINT = "cap_stem_joint"
STEM_CAP_JOINT = "stem_cap_joint"


@dataclass
class Stem(Comparable, Compound, ABC):
    """
    Abstract base class for keycap stems.

    This class provides the foundation for creating the stem part of keycaps.
    It handles the common functionality of stem creation including geometry centering, spatial
    positioning, and joint creation for integration into keycap bodies.

    Parameters
    ----------
    center_at : CenterOf, default=CenterOf.GEOMETRY
        Centering mode for the stem geometry. Determines how the stem is positioned
        relative to its reference point within the keycap. Must be either `CenterOf.GEOMETRY`
        or `CenterOf.BOUNDING_BOX`.
    offset : Location, default=Location()
        Spatial offset for the stem. Allows translation and rotation of the stem
        from its default position within the keycap. Useful for angular adjustments in
        asymmetric keycap designs.

    Attributes
    ----------
    joint : RigidJoint
        The joint connection point for integrating the stem into a keycap body.

    Examples
    --------
    Create a basic MX stem:
    >>> mx_stem = MXStem()

    Create a stem with custom positioning:
    >>> offset_stem = MXStem(offset=Location((0, 0, 1)))

    Notes
    -----
    The Stem class inherits from both Comparable and Compound, enabling comparison
    operations and 3D geometry representation. All concrete implementations must
    provide a _builder method that defines the specific stem geometry.

    Stems are automatically split at the XY plane to remove excess support material.
    """

    center_at: CenterOf = field(default=CenterOf.GEOMETRY)
    offset: Location = field(default_factory=Location)

    def __post_init__(self):
        """
        Initialize the keycap stem after dataclass creation.

        Creates the stem geometry using the concrete implementation's _builder
        method, splits it at the XY plane, and establishes the rigid joint for
        integration into keycap bodies.
        """
        logger.debug("Creating %s", type(self).__name__, extra={"offset": self.offset})
        with self._builder() as p:
            split(bisect_by=Plane.XY, keep=Keep.TOP)
            RigidJoint(STEM_CAP_JOINT)
        super().__init__(obj=p.part.wrapped, label=str(self), joints=p.joints)

    @property
    def joint(self) -> RigidJoint:
        """
        Get the stem's joint for keycap body integration.

        Provides access to the rigid joint that connects the stem to the keycap
        body.

        Returns
        -------
        RigidJoint
            The rigid joint connection point for integrating into keycap bodies.
        """
        return self.joints[STEM_CAP_JOINT]

    @abstractmethod
    def _builder(self) -> BuildPart:
        """
        Construct the stem geometry using BuildPart.

        This abstract method must be implemented by concrete stem classes to
        define the specific geometry for each stem type. The method should
        return a BuildPart context containing the complete stem geometry.

        Returns
        -------
        BuildPart
            The BuildPart context containing the constructed stem geometry.
            This geometry will be processed by the base class to create the
            final stem with proper orientation and joints.

        Notes
        -----
        Implementations may create geometry that extends above and/or below
        the XY plane as needed. The base class will automatically split the
        geometry and retain only the top portion. This allows implementations
        to create base geometry below the XY plane to support CAD operations
        like fillets at the stem base, which require existing geometry to
        fillet against, then removes this support geometry after processing.
        """
        pass

    @property
    def metrics(self) -> MetricLayout[Self]:
        """
        Expose stem properties and dimensions through the `capistry.Comparable` system.

        Provides detailed information about the stem's position, orientation,
        and type.

        Returns
        -------
        MetricLayout
            A metric layout containing a single "Stem" group with metrics for:
            - Type: The stem class name
            - X, Y, Z: Position coordinates in millimeters
            - Rotation: Z-axis rotation in degrees

        """
        glocation = gloc(self)
        return MetricLayout(
            owner=self,
            groups=(
                MetricGroup(
                    "Stem",
                    (
                        Metric("Type", lambda: type(self).__name__),
                        Metric("X", lambda: glocation.position.X, "mm"),
                        Metric("Y", lambda: glocation.position.Y, "mm"),
                        Metric("Z", lambda: glocation.position.Z, "mm"),
                        Metric("Rotation", lambda: glocation.orientation.Z, "°"),
                    ),
                ),
            ),
        )

    def __str__(self) -> str:
        """
        Return a string representation of the stem.

        Provides a simple string representation using the class name,
        which helps identify the stem type during debugging and display.

        Returns
        -------
        str
            The class name of the stem type (e.g., "MXStem", "ChocStem").
        """
        return type(self).__name__


@dataclass
class MXStem(Stem):
    """
    Concrete implementation of a Cherry MX-compatible keycap stem.

    Creates a cylindrical stem with a cross-shaped cavity designed for Cherry MX
    and compatible mechanical keyboard switches. The stem features a main cylinder
    with rounded edges and a cross slot for attachment to MX-style switches.

    Parameters
    ----------
    cylinder_height : float, default=3.8
        Height of the main cylindrical portion of the stem in millimeters.
    cylinder_radius : float, default=2.75
        Radius of the main cylinder in millimeters. Standard value is 5.5mm
        diameter (2.75mm radius) for MX compatibility.
    cross_length : float, default=4.1
        Length of the cross arms in millimeters. This determines the size of
        the cross cavity that interfaces with the switch.
    cross_width : float, default=1.17
        Width of the cross arms in millimeters. Controls the thickness of the
        cross slot for proper switch engagement.
    fillet_stem : float, default=0.25
        Fillet radius for the cross cavity corners in millimeters.
    fillet_outer : float, default=0.25
        Fillet radius for the outer bottom cylinder edge in millimeters.
    center_at : CenterOf, default=CenterOf.GEOMETRY
        Centering mode for the stem geometry.
    offset : Location, default=Location()
        Spatial offset for the stem.

    Examples
    --------
    Create a standard MX stem:
    >>> mx_stem = MXStem()

    Create an MX stem with custom dimensions:
    >>> custom_mx = MXStem(
    ...     cylinder_height=4.0,
    ...     cross_width=1.2,
    ...     fillet_outer=0.3
    ... )
    """

    cylinder_height: float = 3.8
    cylinder_radius: float = 5.5 / 2
    cross_length: float = 4.1
    cross_width: float = 1.17

    fillet_stem: float = 0.25
    fillet_outer: float = 0.25

    def __post_init__(self):
        """Initialize the MX stem after dataclass creation."""
        super().__post_init__()

    @cached_property
    def _cross_sketch(self) -> Sketch:
        """
        Create the cross-shaped cavity sketch.

        Generates a cross-shaped sketch by combining two perpendicular rectangles,
        with filleted corners at the intersection points. This sketch is used to
        subtract material from the stem cylinder to create the switch interface cavity.

        Returns
        -------
        Sketch
            A cross-shaped sketch with filleted corners, sized according to the
            cross_length and cross_width parameters.

        Notes
        -----
        The fillet operation targets the four vertices closest to the origin,
        which are the inner corners of the cross where stress concentration
        would be highest. The sketch is cached for performance optimization.
        """
        with BuildSketch() as sk:
            Rectangle(self.cross_length, self.cross_width)
            Rectangle(self.cross_width, self.cross_length)
            fillet_safe(
                sk.vertices().sort_by(lambda v: v.distance_to(Vertex(0, 0, 0)))[:4],
                self.fillet_stem,
            )
        return sk.sketch

    def _builder(self) -> BuildPart:
        """
        Construct the MX stem geometry.

        Creates the complete MX stem by extruding the cylindrical base, applying
        outer fillets for smooth edges, and subtracting the cross cavity.
        The process includes creating a foundation below the XY plane and the main stem above it.

        Returns
        -------
        BuildPart
            The BuildPart context containing the complete MX stem geometry with:
            - Cylindrical main body with specified height and radius
            - Filleted outer bottom edge
            - Cross-shaped cavity for switch interface
        """
        with BuildSketch() as cyl:
            Circle(self.cylinder_radius)

        with BuildPart() as p:
            extrude(cyl.sketch, self.cylinder_height)
            extrude(offset(cyl.sketch, 2 * self.fillet_outer), -1)

            fillet_safe(
                p.faces()
                .filter_by(lambda f: f.normal_at() == Vector(0, 0, 1))
                .sort_by(Axis.Z)[0]
                .inner_wires()
                .edges(),
                self.fillet_outer,
            )

            extrude(self._cross_sketch, amount=self.cylinder_height, mode=Mode.SUBTRACT)
            split(bisect_by=Plane.XY, keep=Keep.TOP)

        return p


@dataclass
class ChocStem(Stem):
    """
    Concrete implementation of a Kailh Choc V1 compatible keycap stem.

    Creates a specialized stem design for Kailh Choc V1 low-profile switches,
    featuring dual legs with optional arched profiles and cross-shaped support
    structures.

    Parameters
    ----------
    leg_spacing : float, default=5.7
        Distance between the centers of the two legs in millimeters.
    leg_height : float, default=3.0
        Height of the legs in millimeters.
    leg_length : float, default=3.0
        Length (Y-dimension) of each leg in millimeters. Controls the
        front-to-back size of the legs.
    leg_width : float, default=0.95
        Width (X-dimension) of each leg in millimeters. Determines the
        thickness of each leg.
    arc_length_ratio : float, default=0.45
        Ratio of leg length where the arched profile exists (0.0 to 1.0).
        Only used when include_arc is True. Higher values create arcs
        closer to the leg tips.
    arc_width_ratio : float, default=0.25
        Ratio of leg width for arc sagitta depth (0.0 to 1.0). Controls
        how pronounced the leg curvature is when arched legs are enabled.
    cross_length : float, default=3.7
        Length of the cross support arms (Y-dimension) in millimeters.
    cross_width : float, default=0.45
        Width of the cross support arms in millimeters.
    cross_spacing : float, default=4.3
        Spacing between cross support elements in millimeters.
    cross_height : float, default=0.1
        Height of the cross support structure in millimeters. This is typically
        much smaller than the leg height.
    fillet_legs_top : float, default=0.06
        Fillet radius for the top edges of the legs in millimeters.
    fillet_legs_side : float, default=0.08
        Fillet radius for the side edges of the legs in millimeters.
    fillet_legs_bottom : float, default=0.1
        Fillet radius for the bottom edges of the legs in millimeters. Provides
        smooth transitions where legs meet the base.
    include_cross : bool, default=True
        Whether to include the cross support structure.
        Helps raise the keycap to avoid contacting the top housing on key presses.
    include_arc : bool, default=True
        Whether to use arched leg profiles instead of rectangular. Arched
        profiles can reduce stress by avoiding a vacuum forming when trying to remove keycaps.
    center_at : CenterOf, default=CenterOf.GEOMETRY
        Centering mode for the stem geometry.
    offset : Location, default=Location()
        Spatial offset for the stem.

    Examples
    --------
    Create a standard Choc stem:
    >>> choc_stem = ChocStem()

    Create a minimal Choc stem without optional features:
    >>> minimal_choc = ChocStem(
    ...     include_cross=False,
    ...     include_arc=False
    ... )

    Create a custom Choc stem with taller legs:
    >>> tall_choc = ChocStem(
    ...     leg_height=3.5,
    ...     fillet_legs_top=0.1
    ... )

    Create a stem with custom arc curvature:
    >>> curved_choc = ChocStem(
    ...     arc_length_ratio=0.6,
    ...     arc_width_ratio=0.3,
    ...     include_arc=True
    ... )

    Notes
    -----
    The Choc stem design is specifically tailored for Kailh Choc V1 low-profile
    switches.

    The optional arched leg profiles can reduce stress by avoiding a
    vacuum forming when trying to remove keycaps, which may be a problem
    with certain plastics.

    Cross support structures helps raise the keycap a bit to avoid unwanted
    contact upon keypresses.
    """

    leg_spacing: float = 5.7
    leg_height: float = 3
    leg_length: float = 3
    leg_width: float = 0.95

    arc_length_ratio: float = 0.45
    arc_width_ratio: float = 0.25

    cross_length: float = 3.7
    cross_width: float = 0.45
    cross_spacing: float = 4.3
    cross_height: float = 0.1

    fillet_legs_top: float = 0.06
    fillet_legs_side: float = 0.08
    fillet_legs_bottom: float = 0.1

    include_cross: bool = True
    include_arc: bool = True

    def __post_init__(self):
        """Initialize the Choc stem after dataclass creation."""
        super().__post_init__()

    @cached_property
    def _legs_sketch(self) -> Sketch:
        """
        Create the sketch for the stem legs.

        Generates either rectangular or arched leg profiles based on the
        include_arc setting, positioned symmetrically according to leg_spacing.

        Returns
        -------
        Sketch
            A sketch containing two leg profiles positioned symmetrically about
            the origin. Legs can be either rectangular or arched depending on
            the include_arc parameter.

        Notes
        -----
        The sketch is cached to avoid regeneration on multiple accesses.
        When include_arc is True, the method delegates to _legs_arched for
        the more complex curved profile generation.
        """
        locs = GridLocations(self.leg_spacing, 0, 2, 1).locations
        if self.include_arc:
            return self._legs_arched(*locs)

        with BuildSketch(*locs) as sk:
            Rectangle(self.leg_width, self.leg_length)
        return sk.sketch

    def _legs_arched(self, *locs: Location) -> Sketch:
        """
        Create arched leg profiles.

        Generates leg profiles with curved sides using sagitta arcs instead of
        straight edges.

        Parameters
        ----------
        *locs : Location
            Variable number of Location objects specifying where the arched
            legs should be created. Typically two locations.

        Returns
        -------
        Sketch
            A sketch containing arched leg profiles at the specified locations.
            Each leg has curved sides defined by sagitta arcs with curvature
            controlled by arc_length_ratio and arc_width_ratio.

        Notes
        -----
        The arching process:
        1. Calculates arc start position based on arc_length_ratio
        2. Determines sagitta (arc depth) from arc_width_ratio
        3. Creates a polyline and sagitta arc for one side
        4. Mirrors the profile to create the complete symmetric leg shape
        """
        w = self.leg_width / 2
        h = self.leg_length / 2

        arc_h = self.arc_length_ratio * h
        sagitta = self.arc_width_ratio * w

        with BuildSketch(locs) as sk:
            with BuildLine():
                Polyline((0, h), (-w, h), (-w, arc_h))
                SagittaArc((-w, arc_h), (-w, -arc_h), sagitta)
                mirror(about=Plane.XZ)
                mirror(about=Plane.YZ)
            make_face()
        return sk.sketch

    @cached_property
    def _cross_sketch(self) -> Sketch:
        """
        Create the cross support structure sketch.

        Generates a cross-shaped support structure. The cross structure is
        typically much thinner than the main legs but covers a wider area.

        Returns
        -------
        Sketch
            A sketch containing the cross support structure pattern with arms
            extending in both X and Y directions. The pattern is symmetric and
            sized according to cross_spacing, cross_width, and cross_length parameters.

        Notes
        -----
        The cross pattern is created by:
        1. Creating a main horizontal rectangle aligned to one side
        2. Adding vertical rectangles at specific locations
        3. Mirroring the entire pattern for symmetry

        The sketch is cached for performance optimization. The cross support
        is designed to complement the main legs without interfering with the switch interface.
        """
        with BuildSketch(mode=Mode.PRIVATE) as sk:
            Rectangle(self.cross_spacing, self.cross_width, align=(Align.MAX, Align.CENTER))
            with Locations((0, 0), (-self.cross_spacing, 0)):
                Rectangle(self.cross_width, self.cross_length)
            mirror(about=Plane.YZ)
        return sk.sketch

    def _builder(self) -> BuildPart:
        """
        Construct the Choc stem geometry.

        Creates the complete Choc stem including legs with optional arched
        profiles, filleted edges, and optional cross
        support structure.

        Returns
        -------
        BuildPart
            The BuildPart context containing the complete Choc stem geometry with:
            - Dual legs (rectangular or arched)
            - Filleted leg edges
            - Optional cross support structure

        Examples
        --------
        The builder is called automatically during initialization:
        >>> stem = ChocStem()
        >>> # Geometry is built automatically

        Notes
        -----
        The construction process:
        1. Creates a foundation base sized to accommodate all features
        2. Extrudes the leg geometry to the specified height
        3. Applies three different fillet operations:
           - Side edges
           - Top edges
           - Bottom edges
        4. Optionally adds cross support structure if enabled
        """
        with BuildPart() as p:
            with BuildSketch():
                size = max(self.leg_spacing, self.cross_spacing) ** 2
                Rectangle(size, size)

            extrude(amount=-1)
            extrude(self._legs_sketch, amount=self.leg_height)

            fillet_safe(p.edges().group_by(Axis.Z)[-2], self.fillet_legs_side)
            fillet_safe(p.edges().group_by(Axis.Z)[-1], self.fillet_legs_top)

            fillet_safe(
                p.part.faces()
                .filter_by(lambda f: f.normal_at() == Vector(0, 0, 1))
                .sort_by(SortBy.AREA)[-1]
                .inner_wires()
                .edges(),
                self.fillet_legs_bottom,
            )

            if self.include_cross:
                extrude(self._cross_sketch, amount=self.cross_height)

        return p
