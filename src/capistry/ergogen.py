"""
This module provides utilities for generating Ergogen-compatible YAML
configuration files from one or more `capistry.Cap` objects. It translates 3D
geometries into logical keyboard layouts (`points`) and outline shapes
(`outlines`) suitable for use in Ergogen-based keyboard designs.

The output is structured according to Ergogen’s configuration schema,
supporting transformation, spacing, and customizable naming schemes.

Classes
-------
Ergogen : Ergogen-compatible configuration generator.
ErgogenSchema : Defines naming conventions for zones, outlines, rows, and columns.
Points : Represents the full set of layout zones.
Zone : Represents a logical group of rows and columns.
Column : Defines per-column key configuration.
Row : Defines per-row key configuration.
KeyAttrs : Encapsulates shift, rotation, spacing, and padding.
Adjust : Handles shift and rotation adjustments.
Shift : Describes a 2D positional offset.
Point : Describes a 2D point using shift.
OutlineShape : Represents an outline shape path.
YAMLMixin : Base class for YAML serialization.

Functions
---------
_yaml_encoder(float_precision)
    Returns a YAML encoder that formats float values to a given precision.

Examples
--------
Create and export an Ergogen YAML configuration:
>>> cap1 = Cap(...)
>>> cap2 = Cap(...)
>>> ergo = Ergogen(cap1, cap2)
>>> yaml_data = ergo.to_yaml()
>>> print(yaml_data)

Save the configuration to a file:
>>> ergo.write_yaml()

Use a custom naming schema:
>>> from capistry.ergogen import ErgogenSchema
>>> schema = ErgogenSchema(
...     zone_name="left_hand",
...     outline_name="left_hand",
...     row_name="home",
...     column_prefix="col_"
... )
>>> ergo = Ergogen(cap1, cap2, schema=schema)
>>> ergo.write_yaml("left_hand.yaml")

Notes
-----
- All positions and rotations are extracted from the `capistry.Cap`
    objects' 'capistry.Cap.compound' properties.
- The layout is currently limited to a single row and one column per cap.
"""

import logging
from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal as Dec
from itertools import pairwise
from numbers import Number
from typing import Any, Callable, NamedTuple, Self

import yaml
from build123d import Location, Rot, Sketch, Vector, Vertex
from mashumaro.config import BaseConfig
from mashumaro.mixins.yaml import DataClassYAMLMixin, EncodedData
from yaml.nodes import MappingNode, ScalarNode, SequenceNode

from capistry.utils import gloc, is_zeroish

from .cap import Cap

logger = logging.getLogger(__name__)


def _yaml_encoder(float_precision: int | None = None) -> Callable[[Any], str]:
    """
    Create a YAML encoder with custom float precision formatting.

    Parameters
    ----------
    float_precision : int or None, default=None
        Number of decimal places to round floats to. If `None`, floats are not rounded.

    Returns
    -------
    encoder : callable
        A function that takes any serializable object and returns its YAML string representation.
    """

    def encoder(data: Any) -> str:
        class PrecisionDumper(yaml.SafeDumper):
            """Encode data to YAML with custom float precision and formatting."""

            def represent_mapping(self, tag, mapping, flow_style=None) -> MappingNode | ScalarNode:
                if isinstance(mapping, dict) and not mapping:
                    return super().represent_scalar("tag:yaml.org,2002:null", value="")

                return super().represent_mapping(tag, mapping, flow_style)

            def represent_sequence(self, tag, sequence, flow_style=None) -> SequenceNode:
                if all(isinstance(i, Number) for i in sequence):
                    return super().represent_sequence(tag, sequence, flow_style=True)
                return super().represent_sequence(tag, sequence, flow_style)

            def represent_float(self, data: float) -> ScalarNode:
                if float_precision is not None:
                    d = round(Dec(data), float_precision).normalize()
                    if d == int(d):
                        return super().represent_int(int(d))
                    return super().represent_float(float(d))
                return super().represent_float(data)

        PrecisionDumper.add_representer(float, PrecisionDumper.represent_float)
        return yaml.dump(data, Dumper=PrecisionDumper, sort_keys=False, default_flow_style=False)

    return encoder


@dataclass
class YAMLMixin(DataClassYAMLMixin):
    """
    Base mixin for YAML serialization using mashumaro with custom config.

    Configuration ensures omission of `None` values, sorting, and use of aliases
    for serialization.
    """

    class Config(BaseConfig):
        omit_none = True
        omit_default = False
        sort_keys = False
        serialize_by_alias = True


class Shift(NamedTuple):
    """
    Represents a 2D Cartesian shift or offset.

    Parameters
    ----------
    x : float, default=0.0
        X-axis shift.
    y : float, default=0.0
        Y-axis shift.
    """

    x: float = 0.0
    y: float = 0.0

    @classmethod
    def from_vector(cls, v: Vector) -> "Shift":
        """
        Create a Shift from a 2D Vector.

        Parameters
        ----------
        v : Vector
            A Vector object from which to extract the X and Y components.

        Returns
        -------
        Shift
            A new Shift object.
        """
        return Shift(x=v.X, y=v.Y)

    def __iter__(self):
        return iter([self.x, self.y])

    def __add__(self, other: Self) -> "Shift":
        return Shift(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Self) -> "Shift":
        return Shift(self.x - other.x, self.y - other.y)


@dataclass
class Adjust(YAMLMixin):
    """
    Adjustment configuration containing optional shift and rotation.

    Parameters
    ----------
    shift : Shift or None, default=None
        A 2D shift.
    rotate : float or None, default=None
        Rotation angle in degrees.
    """

    shift: Shift | None = None
    rotate: float | None = None

    def __pre_serialize__(self) -> Self:
        """
        Normalize the object before YAML serialization.

        Returns
        -------
        Self
            The cleaned-up Adjust object with zero-equivalent fields set to None.
        """
        if isinstance(self.shift, Shift) and is_zeroish(*self.shift):
            self.shift = None
        if isinstance(self.rotate, float) and is_zeroish(self.rotate):
            self.rotate = None
        return self

    @classmethod
    def from_location(cls, loc: Location) -> "Adjust | None":
        """
        Generate an Adjust object from a build123d Location object.

        Parameters
        ----------
        loc : Location
            A build123d Location object with position and orientation.

        Returns
        -------
        Adjust or None
            A new Adjust object or None if no adjustment is required.
        """
        pos = Vector(0, 0, loc.position.Z)
        orient = Vector(loc.orientation.X, loc.orientation.Y, 0)

        if loc.position == pos and loc.orientation == orient:
            return None

        return Adjust(shift=Shift.from_vector(loc.position), rotate=-loc.orientation.Z)


@dataclass
class KeyAttrs(Adjust):
    """
    Key attributes including adjustment, spread, and padding.

    Parameters
    ----------
    shift : Shift or None, default=None
        Position shift.
    rotate : float or None, default=None
        Rotation angle.
    spread : float or None, default=None
        Horizontal distance between keys.
    padding : float or None, default=None
        Vertical distance between keys.
    """

    spread: float | None = None
    padding: float | None = None

    @classmethod
    def from_location(
        cls, loc: Location, spread: float | None = None, padding: float | None = None
    ) -> "KeyAttrs":
        """
        Create KeyAttrs from a Location and optional spacing values.

        Parameters
        ----------
        loc : Location
            Build123d Location object used to derive shift and rotation.
        spread : float or None, default=None
            Optional spread value.
        padding : float or None, default=None
            Optional padding value.

        Returns
        -------
        KeyAttrs
            A new KeyAttrs instance.
        """
        adjust = Adjust.from_location(loc)
        return KeyAttrs(
            shift=adjust.shift if adjust else None,
            rotate=adjust.rotate if adjust else None,
            spread=spread,
            padding=padding,
        )


@dataclass
class Point(YAMLMixin):
    """
    A 2D point defined by a shift vector.

    Parameters
    ----------
    shift : Shift, default=Shift()
        2D offset from origin.
    """

    shift: Shift = field(default_factory=Shift)

    @classmethod
    def from_shift(cls, x: float = 0.0, y: float = 0.0) -> Self:
        """
        Create a Point using X and Y values.

        Parameters
        ----------
        x : float, default=0.0
            X coordinate.
        y : float, default=0.0
            Y coordinate.

        Returns
        -------
        Point
            A new Point instance.
        """
        return cls(shift=Shift(x, y))

    @classmethod
    def from_vertex(cls, v: Vertex) -> Self:
        """
        Create a Point from a build123d Vertex object's X and Y position.

        Parameters
        ----------
        v : Vertex
            A build123d Vertex.

        Returns
        -------
        Point
            A new Point instance.
        """
        return cls(shift=Shift(v.X, v.Y))


@dataclass
class OutlineShape(YAMLMixin):
    """
    Defines an outline shape in an Ergogen configuration.

    Parameters
    ----------
    what : str, default="polygon"
        The type of shape (e.g., "polygon").
    where : str or bool, default=False
        Location identifier such as a key reference or a filter.
    adjust : Adjust or None, default=None
        Transformations to apply to the shape.
    points : list of Point, default=[]
        List of points defining the shape's path.
    """

    what: str = field(default="polygon")
    where: str | bool = field(default=False)
    adjust: Adjust | None = None
    points: list[Point] = field(default_factory=list)

    @classmethod
    def from_sketch(cls, sketch: Sketch, where: str, adjust: Adjust | None = None) -> Self:
        """
        Convert a build123d Sketch object into an OutlineShape object.

        Parameters
        ----------
        sketch : Sketch
            Build123d sketch object.
        where : str
            Location Identifier for the shape placement.
        adjust : Adjust or None, default=None
            Optional transformation.

        Returns
        -------
        OutlineShape
            A new OutlineShape derived from the sketch.
        """
        points = [Point.from_vertex(v) for v in sketch.vertices()]
        if not points:
            logger.debug("Empty sketch provided, returning empty %s", type(cls).__name__)
            return cls(points=[])

        points = [points[0]] + [
            Point(shift=curr.shift - prev.shift) for prev, curr in pairwise(points)
        ]

        logger.debug(f"Created {type(cls).__name__} with {len(points)} points.")
        return cls(points=points, where=where, adjust=adjust)


@dataclass
class Column(YAMLMixin):
    """
    Column definition for an Ergogen layout.

    Parameters
    ----------
    key : KeyAttrs or None, default=None
        Key-level attributes specific to this column.
    """

    key: KeyAttrs | None = None


@dataclass
class Row(KeyAttrs):
    """
    Row definition for an Ergogen layout.

    Inherits from KeyAttrs.
    """


@dataclass
class Zone(YAMLMixin):
    """
    A layout zone containing keys, columns, and rows.

    Parameters
    ----------
    key : KeyAttrs, default=KeyAttrs()
        Default key configuration for zone.
    columns : dict of str to Column, default={}
        Mapping of column names to their configurations.
    rows : dict of str to Row, default={}
        Mapping of row names to their configurations.
    """

    key: KeyAttrs = field(default_factory=KeyAttrs)
    columns: dict[str, Column] = field(default_factory=dict)
    rows: dict[str, Row] = field(default_factory=dict)


@dataclass
class Points(YAMLMixin):
    """
    Ergogen points configuration containing all layout zones.

    Parameters
    ----------
    zones : dict of str to Zone, default={}
        Mapping of zone names to their corresponding Zone objects.
    """

    zones: dict[str, Zone] = field(default_factory=dict)

    @classmethod
    def from_zone(cls, zone_name: str, zone: Zone):
        """
        Create a Points object from a single Zone.

        Parameters
        ----------
        zone_name : str
            Name of the zone.
        zone : Zone
            Zone object to be added.

        Returns
        -------
        Points
            A new Points configuration with the specified zone.
        """
        return Points(zones={zone_name: zone})


@dataclass
class ErgogenSchema:
    """
    Schema configuration for Ergogen config generation.

    Parameters
    ----------
    zone_name : str, default="capistry"
        Name used for the zone.
    outline_name : str, default="capistry"
        Name used for outline.
    row_name : str, default="row"
        Default row name.
    column_prefix : str, default="col_"
        Prefix used to generate column names.
    """

    zone_name: str = "capistry"
    outline_name: str = "capistry"
    row_name: str = "row"
    column_prefix: str = "col_"


@dataclass
class ErgogenConfig(YAMLMixin):
    """
    Internal representation of an Ergogen-compatible YAML configuration.

    This class holds the core sections of the Ergogen YAML file. It is not
    intended for direct use by end users, but serves as a composable
    serialization-friendly container for generated layout data.

    Parameters
    ----------
    points : Points
        The logical layout of keys, organized into zones, rows, and columns.
        This section maps directly to Ergogen's `points` block.
    outlines : dict of str to list of OutlineShape
        The visual geometry of the keyboard layout. Each key's outline is stored
        as a shape, grouped under a named outline layer. This maps to Ergogen's
        `outlines` block.

    Examples
    --------
    >>> config = ErgogenConfig(points=Points(...), outlines={"main": [OutlineShape(...)]})
    >>> print(config.to_yaml())
    """

    points: Points
    outlines: dict[str, list[OutlineShape]]


@dataclass(init=False)
class Ergogen:
    """
    Generates Ergogen-compatible keyboard YAML configuration files
    from one or more `capistry.Cap` objects.

    Parameters
    ----------
    *caps : Cap
        One or more `Cap` instances representing individual keys or units.
    schema : ErgogenSchema, optional
        Schema defining naming conventions for zones, outlines, rows, and columns.
        Defaults to a standard schema if not provided.

    Attributes
    ----------
    caps : list[Cap]
        The list of Caps used to build the layout.
    schema : ErgogenSchema
        Naming schema applied during generation (not serialized).
    _config : ErgogenConfig
        Internal YAML-ready configuration, lazily built on access.

    Raises
    ------
    ValueError
        If no Caps are provided at initialization.

    Examples
    --------
    Create 2 caps and export an Ergogen config
    >>> cap1 = Cap(...)
    >>> cap2 = Cap(...)
    >>> ergo = Ergogen(cap1, cap2)
    >>>
    >>> # Print the YAML string
    >>> yaml_str = ergo.to_yaml()
    >>> print(yaml_str)
    >>>
    >>> # Write the YAML to file
    >>> ergo.write_yaml("config.yaml")
    """

    caps: list[Cap] = field(default_factory=list)
    schema: ErgogenSchema = field(default_factory=ErgogenSchema)

    def __init__(self, *caps: Cap, schema: ErgogenSchema | None = None):
        self.caps = list(caps)
        self.schema = schema or ErgogenSchema()

        if not self.caps:
            raise ValueError("At least one Cap must be provided.")

    @property
    def _config(self) -> ErgogenConfig:
        logger.info(f"Creating {type(self).__name__} config for {len(self.caps)} cap(s)")

        schema = self.schema
        zone = Zone(key=KeyAttrs(spread=0, padding=0))
        offset: Vector | None = None

        points = Points.from_zone(schema.zone_name, zone)
        outlines: dict[str, list[OutlineShape]] = {schema.outline_name: []}

        for i, cap in enumerate(self.caps):
            outline = deepcopy(cap.outline)
            outline.position = -cap.stem.position

            key_loc = gloc(cap.stem)
            offset = offset or key_loc.position
            key_loc.position -= offset

            rot = Rot(cap.outline.orientation - cap.stem.orientation)
            col_name = f"{schema.column_prefix}{i + 1}"

            zone.columns[col_name] = Column(key=KeyAttrs.from_location(key_loc))
            zone.rows[schema.row_name] = Row()

            where = f"{schema.zone_name}_{col_name}_{schema.row_name}"

            outlines[schema.outline_name].append(
                OutlineShape.from_sketch(
                    sketch=outline,
                    where=where,
                    adjust=Adjust.from_location(rot),
                )
            )

        return ErgogenConfig(points=points, outlines=outlines)

    def to_yaml(self, precision: int = 3) -> EncodedData:
        """
        Convert the Ergogen configuration to a YAML-formatted string.

        Parameters
        ----------
        precision : int, default=3
            Number of decimal places for floating-point values in the output.

        Returns
        -------
        EncodedData
            A string-like object containing the YAML configuration.
        """
        return self._config.to_yaml(encoder=_yaml_encoder(float_precision=precision))

    def write_yaml(self, filepath: str = "config.yaml", precision: int = 3) -> None:
        """
        Write the Ergogen configuration to a YAML file.

        Parameters
        ----------
        filepath : str, default="config.yaml"
            Path to the output file.
        precision : int, default=3
            Number of decimal places for floating-point values in the file.
        """
        yaml_str = self.to_yaml(precision=precision)
        with open(filepath, "w") as f:
            f.write(str(yaml_str))
