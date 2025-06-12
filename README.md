
<h1 align="center"> Capistry </h1>

<p align="center">
  <em>
    A Python package for parametric 3D modeling of keyboard keycaps using
    <a href="https://github.com/gumyr/build123d">build123d</a>.
  </em>
</p>

<p align="center">
  <a href="https://larssont.github.io/capistry/capistry.html"><img src="https://img.shields.io/badge/docs-available-brightgreen?style=flat" alt="Docs"></a>
  <img src="https://img.shields.io/badge/License-MPL%202.0-brightgreen.svg" alt="License: MPL 2.0">
  <img src="https://img.shields.io/pypi/v/capistry" alt="PyPI Version">
  <img src="https://img.shields.io/badge/python-3.13+-blue.svg?style=flat" alt="Python 3.13+">
</p>

<p align="center">
  <img 
      src="assets/img/cover.png" 
      style="max-width: 480px; width: 80%" 
      alt="Rendered keycap model created with Capistry"
  />
</p>

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Features](#features)
- [Documentation](#documentation)
- [Examples](#examples)
- [License](#license)
- [Contributing](#contributing)
- [Acknowledgments](#acknowledgments)


## Overview

- **Parametric Design**: Create custom keycaps with precise control over dimensions, angles, and styling.
- **Shapes**: Rectangular, slanted, skewed, and trapezoidal keycap shapes.
- **Stems**: Compatible with MX and Choc switches.
- **Advanced Geometry**: Tapers, fillets, and surface modeling.
- **Batching**: Generate panels of multiple keycaps for 3D printing.
- **Exporting**: Export to any format supported by build123d, including STL, STEP, DXF, SVG, and more.
- **Ergogen**: Export `Ergogen` configurations consisting of keycap positions and outlines.
- **Extensible**: Designed to be extensible - you can create custom stems, cap classes, fillet strategies, and sprue designs by extending the base classes.

## Installation

```bash
pip install capistry
```

### Requirements

- Python 3.13+
- Dependencies:
    - build123d
    - rich
    - mashumaro
    - more-itertools
    - attrs
    - tzdata

## Quick Start

```python
from build123d import *
from capistry import *
import logging

# Initialize logging
init_logger(level=logging.INFO)

# Create a basic rectangular keycap
cap = RectangularCap(
    width=18,
    length=18,
    height=5,
    wall=1.25,
    roof=1.25,
    taper=Taper.uniform(7),
    stem=MXStem(center_at=CenterOf.GEOMETRY),
    fillet_strategy=FilletUniform()
)

# Export as STL
export_stl(cap.compound, "keycap.stl")

# Create a sprued grid-like panel for 3D printing
panel = Panel(
    items=[
        PanelItem(cap, quantity=10, mirror=True),
    ],
    sprue=SprueCylinder(),
)

# Export panel as STL
export_stl(panel.compound, "panel.stl")
```

> [!TIP]
> You can use [`ocp-vscode`](https://pypi.org/project/ocp-vscode/) to preview your parts in VS-Code during development.

## Features

### Keycap Shapes

As of now, all keycap shapes are quadrilaterals, i.e. four-sided polygons.

#### `RectangularCap`
Standard rectangular keycap:
```python
cap = RectangularCap(width=18, length=18, height=5)
```

#### `SlantedCap`
An asymmetric keycap where two sides are angled evenly away from their respective orientations. The resulting shape has two orthogonal (90°) corners, one corner at 90 + v° and another at 90 – v°, where v is the slant angle.
```python
cap = SlantedCap(width=18, length=18, height=5, angle=7)
```

#### `SkewedCap`
Keycap with a parallelogram shape:
```python
cap = SkewedCap(width=18, length=18, height=5, skew=5, skew_width=True)
```

#### `TrapezoidCap`
Keycap with a trapezoidal shape:
```python
cap = TrapezoidCap(width=18, length=18, height=5, angle=5)
```

### Stems
Support for different stems:
```python
# MX-style stem
stem = MXStem()

# Choc-style stem
stem = ChocStem()

cap = RectangularCap(stem=stem)
```

### Tapering
Control the slope of keycap sides:
```python
# Uniform taper on all sides
taper = Taper.uniform(7)

# Side-specific tapering
taper = Taper(front=10, back=7, left=4, right=4)

cap = RectangularCap(taper=taper)
```

### Fillet Strategies
Choose how edges are rounded:
```python
# Uniform filleting
fillet_strat = FilletUniform()

# Sides-first filleting
fillet_strat = FilletSidesFirst()

# Sides-Last filleting
fillet_strat = FilletSidesFirst()

cap = RectangularCap(fillet_strategy=fillet_strat)
```

> [!WARNING]
> Due to the nature of CAD modeling, some fillet configurations simply won't be compatible with every combination of cap, taper and surface due to geometric constraints. If you run into issues building a certain cap, try to adjust these parameters to resolve the problem. `FilletUniform` tends to be the least error-prone strategy.

### Surface Modeling
The top face of keycaps can be precisely modeled by defining a `Surface`. A `Surface` is represented by a matrix (a 2-dimensional list), specifying the offset values which will be used to model the top face. Optionally, a weights matrix may also be supplied.

```python
surface = Surface(
        [
            [4, 4, 4, 4],
            [2, -1, -1, 2],
            [0, -1, -1, 0],
            [0, 0, 0, 0],
        ]
    )

cap = TrapezoidCap(surface=surface)
```

### Comparisons
You can compare caps, fillets, stems, and surfaces using the `capistry.Comparer` class. This is useful for identifying both dimensional differences and property variations.

```python
# Create two keycaps with different parameters
c1 = RectangularCap(width=18, length=18, height=5)
c2 = RectangularCap(width=19*2 - 1, length=18, height=5)

# Create a comparer
comparer = Comparer(c2, c2)

# Show the comparison, outputs a rich table in the console
comparer.show(show_deltas=True)
```

### Panel Generation
Create grid-like panels of keycaps for simpler 3D printing by creating a `capistry.Panel`:
```python
cap = RectangularCap()

# Create a 4x4 panel of a keycap
panel = Panel(
    items=[PanelItem(cap, quantity=16)], 
    sprue=SprueCylinder(), 
    cols=4
)

# Export the entire panel
export_stl(panel.compound, "keycap_panel.stl")
```

### Ergogen Export
Export your keycaps in their current locations to an `Ergogen` configuration file.
```python
# Create two rectangular keycaps
c1 = RectangularCap()
c2 = RectangularCap()

# Position the second keycap to the right of the first
c2.locate(c1.top_right)

#  Create an ergogen instance, and write the configuration to a YAML file
ergogen = Ergogen(c1, c2)
ergogen.write_yaml("config.yaml", precision=3)
```

## Documentation

Full API documentation is available and generated using [pdoc](https://pdoc.dev).

👉 [**View the full documentation here**](https://larssont.github.io/capistry/)

## Examples

For more detailed examples, see the [examples/](examples/) directory in the repository.

## Development

### Building from Source
```bash
git clone https://github.com/larssont/capistry.git
cd capistry
uv sync
```

## License

This project is licensed under the Mozilla Public License 2.0 - see the [LICENSE.md](LICENSE.md) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- [build123d](https://github.com/gumyr/build123d) — CAD library powering Capistry
