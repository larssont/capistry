"""
.. include:: ../../README.md
"""  # noqa: D200, D400

from .cap import Cap, RectangularCap, SkewedCap, SlantedCap, TrapezoidCap
from .compare import BaseComparer, Comparer
from .ergogen import Ergogen, ErgogenSchema
from .fillet import (
    FilletDepthWidth,
    FilletMiddleTop,
    FilletStrategy,
    FilletUniform,
    FilletWidthDepth,
    fillet_safe,
)
from .logger import init_logger
from .panel import Panel, PanelItem
from .sprue import Sprue, SprueCylinder, SpruePolygon
from .stem import ChocStem, MXStem, Stem
from .surface import Surface
from .taper import Taper

__all__ = [
    "BaseComparer",
    "Cap",
    "ChocStem",
    "Comparer",
    "Ergogen",
    "ErgogenSchema",
    "FilletDepthWidth",
    "FilletMiddleTop",
    "FilletStrategy",
    "FilletUniform",
    "FilletWidthDepth",
    "MXStem",
    "Panel",
    "PanelItem",
    "RectangularCap",
    "SkewedCap",
    "SlantedCap",
    "Sprue",
    "SprueCylinder",
    "SpruePolygon",
    "Stem",
    "Surface",
    "Taper",
    "TrapezoidCap",
    "fillet_safe",
    "init_logger",
]
