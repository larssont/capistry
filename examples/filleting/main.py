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

stem = ChocStem()
taper = Taper.uniform(7)

c1 = RectangularCap(
    width=width,
    length=length,
    height=height,
    wall=wall,
    roof=roof,
    taper=taper,
    stem=stem,
    fillet_strategy=FilletUniform(),  # Uniform fillet, every outside edge gets the same radius
)

# Fillet left-to-right, then front-to-back
c2 = c1.clone()
c2.fillet_strategy = FilletWidthDepth()
c2.build()
c2.locate(c1.top_right * Pos(X=gap))

# Fillet front-to-back, then left-to-right
c3 = c1.clone()
c3.fillet_strategy = FilletDepthWidth()
c3.build()
c3.locate(c2.top_right * Pos(X=gap))

# Fillet middle edges first, then top perimeter
c4 = c1.clone()
c4.fillet_strategy = FilletMiddleTop()
c4.build()
c4.locate(c3.top_right * Pos(X=gap))

caps = [c1.compound, c2.compound, c3.compound, c4.compound]

show(*caps)


export_stl(Compound(caps), file_path=Path(__file__).parent / "caps.stl")
