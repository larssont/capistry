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
taper = Taper.uniform(7)
fillet_strat = FilletUniform()

cap = SlantedCap(
    width=width,
    length=length,
    height=height,
    wall=wall,
    roof=roof,
    taper=taper,
    stem=stem,
    fillet_strategy=fillet_strat,
    angle=angle,
)


# Create a panel of 8 normal caps, and 8 mirrored  ones
panel = Panel(items=[PanelItem(cap, quantity=8, mirror=True)], sprue=SprueCylinder(), col_count=4)

# Show the panel
show(panel.compound)

# Export the panel to .STL
export_stl(panel.compound, file_path=Path(__file__).parent / "caps.stl")
