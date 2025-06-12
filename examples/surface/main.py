# ruff: noqa: F403, F405

import logging
from pathlib import Path

from build123d import *
from ocp_vscode import *

from capistry import *

init_logger(level=logging.INFO)

# Camera defaults for ocp_vscode
set_defaults(
    reset_camera=Camera.KEEP,
    default_color=(10, 125, 100),
    default_edgecolor=(70, 55, 55),
    default_opacity=0.75,
    transparent=True,
    metalness=0.50,
    roughness=0.45,
)

width = 18
length = 18
wall = 1.25
roof = 1.25
height = 5
gap = 1
angle = -7

stem = MXStem(center_at=CenterOf.GEOMETRY)
taper = Taper(12, 0, 4, 4)
fillet_strat = FilletUniform()

# Top surface:
# - Concave center
# - Tilted right
surface = Surface(
    [
        [1.25, 0.6, 0.6, 0.8],
        [0.65, -0.4, -0.4, 0],
        [0.65, -0.6, -0.6, 0],
        [0.65, -0.6, -0.6, 0],
        [0.65, -0.4, -0.4, 0],
        [0.8, 0.2, 0.2, 0.2],
    ]
).tilted(0.25)

c1 = SlantedCap(
    width=width,
    length=length,
    height=height,
    wall=wall,
    roof=roof,
    taper=taper,
    stem=stem,
    surface=surface,
    fillet_strategy=fillet_strat,
    angle=angle,
)

c2 = c1.mirrored().locate(c1.top_right * Pos(X=gap))

cap_parts = [c1.compound, c2.compound]
show(*cap_parts)

export_stl(Compound(cap_parts), file_path=Path(__file__).parent / "caps.stl")
