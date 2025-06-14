import logging
from pathlib import Path

from build123d import *
from ocp_vscode import *

from capistry import *

init_logger(level=logging.INFO)

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
skew = 12

stem = ChocStem()
taper = Taper(12, 0, 4, 4)
fillet_strat = FilletUniform()

caps: list[Cap] = [
    SkewedCap(
        width=width,
        length=length,
        height=height,
        roof=roof,
        wall=wall,
        skew=skew,
        taper=taper,
        fillet_strategy=fillet_strat,
        stem=stem,
    )
]

cap_count = 4

for _ in range(cap_count - 1):
    cap = caps[-1].mirrored()
    cap.locate(caps[-1].top_right * Pos(gap))
    caps.append(cap)

cap_parts = [c.compound for c in caps]

show(*cap_parts)
export_stl(Compound(cap_parts), file_path=Path(__file__).parent / "caps.stl")
