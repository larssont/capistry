"""
Arranges Cap objects into a grid-like panel layout using build123d.

The panel organizes caps into rows and columns with optional mirrored variants,
automatically determining an optimal column count when not specified.

Sprues can be inserted between adjacent caps to ensure parts meet manufacturing
requirements (e.g., minimum printable size). Sprue generation
is handled via internal `sprue` classes and applied between rows and columns.

Rich progress bars are used to visualize the placement of caps and addition of sprues
during compound assembly.

Classes
-------
PanelItem : dataclass
    Encapsulates one or more identical caps, with optional mirroring.
Panel : dataclass
    Constructs the full panel compound with optional sprues and layout control.
PanelProgress : dataclass
    Context manager for tracking panel generation progress.

Examples
--------
>>> # Create a simple panel with multiple caps
>>> cap = SkewedCap()
>>> items = [PanelItem(cap, quantity=5)]
>>> panel = Panel(items, col_count=3)
>>> compound = panel.compound
"""

import logging
from copy import copy
from dataclasses import dataclass, field
from functools import cached_property

from build123d import Compound, Pos, Vector
from more_itertools import chunked, flatten, last, lstrip, pairwise, rstrip
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)

from capistry._math import divisors

from .cap import Cap
from .sprue import Sprue, SprueCylinder

logger = logging.getLogger(__name__)


@dataclass
class PanelProgress:
    """
    Context manager that tracks and displays progress using Rich's progress bar.

    Tracks both cap placement and sprue generation phases during panel assembly,
    providing visual feedback for long-running operations. Progress tracking can
    be disabled.

    Parameters
    ----------
    disable : bool, default=False
        If True, disables all progress tracking and display.
    caps : int, default=0
        Total number of caps to be placed in the panel.
    sprues : int, default=0
        Total number of sprues to be generated for connections.

    Attributes
    ----------
    _progress : Progress or None
        Internal Rich Progress instance for display management.
    _arrange_task : TaskID or None
        Task identifier for cap arrangement progress.
    _sprue_task : TaskID or None
        Task identifier for sprue generation progress.

    Examples
    --------
    >>> with PanelProgress(caps=10, sprues=5) as progress:
    ...     for i in range(10):
    ...         # Place cap logic here
    ...         progress.arrange()
    ...     for i in range(5):
    ...         # Add sprue logic here
    ...         progress.sprue()
    """

    disable: bool = False
    caps: int = 0
    sprues: int = 0

    _progress: Progress | None = None
    _arrange_task: TaskID | None = None
    _sprue_task: TaskID | None = None

    def __enter__(self):
        """
        Initialize the Rich progress UI context.

        Creates progress bars for cap arrangement and sprue generation if
        progress tracking is enabled and counts are greater than zero.

        Returns
        -------
        PanelProgress
            Self-reference for context manager protocol.
        """
        if self.disable:
            return self

        self._progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            transient=True,
        )
        self._progress.__enter__()

        if self.caps > 0:
            self._arrange_task = self._progress.add_task(
                "[green]Arranging caps...", total=self.caps
            )
        if self.sprues > 0:
            self._sprue_task = self._progress.add_task("[cyan]Adding sprues...", total=self.sprues)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit and clean up the progress context.

        Parameters
        ----------
        exc_type : type or None
            Exception type if an exception occurred.
        exc_val : Exception or None
            Exception instance if an exception occurred.
        exc_tb : traceback or None
            Traceback object if an exception occurred.
        """
        if self._progress:
            self._progress.__exit__(exc_type, exc_val, exc_tb)
            self._progress = None
            self._arrange_task = None
            self._sprue_task = None

    def arrange(self, amount: int = 1):
        """
        Advance the cap placement progress bar.

        Parameters
        ----------
        amount : int, default=1
            Number of caps that have been placed since last update.
        """
        if self._progress and self._arrange_task is not None:
            self._progress.update(self._arrange_task, advance=amount, refresh=True)

    def sprue(self, amount: int = 1):
        """
        Advance the sprue connection progress bar.

        Parameters
        ----------
        amount : int, default=1
            Number of sprues that have been added since last update.
        """
        if self._progress and self._sprue_task is not None:
            self._progress.update(self._sprue_task, advance=amount, refresh=True)


@dataclass
class PanelItem:
    """
    Represents a group of identical caps with optional mirrored variants.

    Handles duplication and mirroring of caps based on configuration,
    supporting both regular and mirrored versions of the same cap design.

    Parameters
    ----------
    cap : Cap
        The base cap object to be duplicated and/or mirrored.
    quantity : int, default=1
        Number of regular (non-mirrored) caps to include.
    mirror : bool, default=False
        If True, include mirrored versions in addition to regular caps.
    mirror_only : bool, default=False
        If True, include only mirrored versions (ignores quantity for regular caps).
    mirror_quantity : int or None, default=None
        Number of mirrored caps to include. If None, uses same as quantity.

    Attributes
    ----------
    cap : Cap
        Cloned and repositioned version of the input cap.

    Examples
    --------
    >>> cap = Cap()
    >>> # Create 3 regular caps
    >>> item1 = PanelItem(cap, quantity=3)
    >>>
    >>> # Create 2 regular + 2 mirrored caps
    >>> item2 = PanelItem(cap, quantity=2, mirror=True)
    >>>
    >>> # Create only 1 mirrored cap
    >>> item3 = PanelItem(cap, mirror_only=True)
    >>>
    >>> # Get all expanded caps
    >>> all_caps = item2.expanded  # Returns list of 4 Cap objects
    """

    cap: Cap
    quantity: int = 1
    mirror: bool = False
    mirror_only: bool = False
    mirror_quantity: int | None = None

    def __post_init__(self):
        """
        Post-initialization processing.

        Clones the input cap and resets its position to origin to ensure
        each panel item starts from a clean state.
        """
        self.cap = self.cap.clone()
        self.cap.locate(Pos())

    @property
    def expanded(self) -> list[Cap]:
        """
        Return a list of all Cap instances, including mirrored ones if configured.

        Generates the full list of caps based on quantity settings and mirroring
        options. Each cap is a separate copy to avoid shared location issues.

        Returns
        -------
        list of Cap
            All cap instances that should be included in the panel layout.
            Order is regular caps first, then mirrored caps.

        Notes
        -----
        The method respects the mirror_only flag by excluding regular caps
        when it's True. Mirror quantity defaults to the regular quantity if
        not explicitly specified.
        """
        caps: list[Cap] = []
        logger.debug(
            "Expanding %s",
            type(self).__name__,
            extra={
                "quantity": self.quantity,
                "mirror": self.mirror,
                "mirror_only": self.mirror_only,
                "cap": type(self.cap).__name__,
            },
        )
        if not self.mirror_only:
            caps.extend(copy(self.cap) for _ in range(self.quantity))

        if self.mirror or self.mirror_only:
            qty = self.quantity if self.mirror_quantity is None else self.mirror_quantity
            mirrored = self.cap.mirrored()
            caps.extend(copy(mirrored) for _ in range(qty))
        return caps


@dataclass
class Panel:
    """
    Represents a 2D layout of caps and optional sprues arranged in rows and columns.

    Automatically determines optimal column count when not specified and provides
    progress tracking during generation. The panel arranges caps in a grid pattern
    with optional sprue connections between adjacent parts for manufacturing support.

    Parameters
    ----------
    items : list of PanelItem
        List of panel items to be arranged in the layout.
    col_count : int or None, default=None
        Number of columns in the grid. If None, automatically determined based
        on total item count and maximum column limit.
    sprue : Sprue or None, default=SprueCylinder()
        Sprue object for connecting adjacent caps. Set to None to disable sprues.
    gap : float, default 1.0
        Spacing between adjacent caps in the layout.
    show_progress : bool, default=True
        Whether to display progress bars during panel generation.

    Attributes
    ----------
    _max_cols : int
        Maximum number of columns allowed in automatic layout (default 10).

    Examples
    --------
    >>> # Create panel with automatic column detection
    >>> items = [PanelItem(Cap(), quantity=12)]
    >>> panel = Panel(items)
    >>> compound = panel.compound
    >>>
    >>> # Create panel with specific layout
    >>> panel = Panel(items, col_count=4, gap=2.0, show_progress=False)
    >>> compound = panel.compound
    """

    _max_cols: int = field(default=10, init=False)

    items: list[PanelItem]
    col_count: int | None = None
    sprue: Sprue | None = SprueCylinder()
    gap: float = 1
    show_progress: bool = True

    def __post_init__(self):
        """
        Post-initialization processing.

        Sets the column count to the optimal value if not explicitly provided,
        ensuring reasonable grid proportions for the given number of items.
        """
        if self.col_count is None:
            self.col_count = self._optimal_col_count

    @property
    def _optimal_col_count(self) -> int:
        """
        Compute a reasonable number of columns based on item count and max limit.

        Uses divisors to try and find column counts that create
        rectangular grids without uneven rows, while respecting
        the maximum column constraint.

        Returns
        -------
        int
            Optimal number of columns for the current item count.

        Notes
        -----
        The algorithm finds divisors of the total item count, filters out
        those that would create too many columns or rows, and selects the
        largest valid divisor.
        """
        count = len(self._flattened)
        divs = list(
            lstrip(
                rstrip(divisors(count), lambda n: n > self._max_cols),
                lambda n: count // n > self._max_cols,
            )
        )
        return last(divs, self._max_cols)

    @cached_property
    def _flattened(self) -> list[Cap]:
        """
        Flatten and expand all caps from panel items into a single list.

        Returns
        -------
        list of Cap
            All individual cap objects that will be placed in the panel.
        """
        return list(flatten(i.expanded for i in self.items))

    @cached_property
    def compound(self) -> Compound:
        """
        Construct the full compound of the panel, including sprues if configured.

        Generates the complete 3D compound by arranging caps in a grid layout
        and adding sprue connections between adjacent parts. Progress is tracked
        and displayed unless disabled.

        Returns
        -------
        build123d.Compound
            Complete panel compound containing all caps and sprues arranged
            in the specified layout.

        Notes
        -----
        The compound is cached after first generation to avoid recomputation.
        Horizontal sprues connect caps within each row, while vertical sprues
        connect the first cap of each row to create a connected structure.
        """
        rows = list(chunked(self._flattened, self.col_count))

        caps = len(self._flattened)
        sprues = sum(len(r) - 1 for r in rows) + len(rows) - 1

        with PanelProgress(not self.show_progress, caps, sprues) as p:
            return self._assemble(rows, p)

    def _assemble(self, rows: list[list[Cap]], progress: PanelProgress) -> Compound:
        """
        Assemble the layout row-by-row, placing caps and connecting sprues.

        Places each cap at the appropriate grid position and generates sprue
        connections between adjacent caps both horizontally and vertically.

        Parameters
        ----------
        rows : list of list of Cap
            Caps organized into rows for grid placement.
        progress : PanelProgress
            Progress tracker for visual feedback during assembly.

        Returns
        -------
        build123d.Compound
            Assembled compound containing all positioned caps and sprues.
        """
        sprued = Compound(label="Sprues")
        cursor = Vector()

        logger.info(
            "Assembling panel with %d cap(s) and %d sprue(s)", progress.caps, progress.sprues
        )

        for row in rows:
            y_diff = 0
            for i, cap in enumerate(row):
                y_diff = max(y_diff, cap.size.Y)
                self._place(cap, cursor)
                cursor += Vector(cap.size.X + self.gap)
                progress.arrange()

                if self.sprue and i > 0:
                    self.sprue.connect_horizontally(row[i - 1], cap).parent = sprued
                    progress.sprue()

            cursor.X = 0
            cursor.Y -= y_diff + self.gap

        if self.sprue:
            for a, b in pairwise(rows):
                self.sprue.connect_vertically(a[0], b[0]).parent = sprued
                progress.sprue()

        return Compound(children=[c.compound for c in flatten(rows)] + [sprued])

    def _place(self, cap: Cap, pos: Vector):
        """
        Place a cap in the layout at the given position.

        Positions the cap by calculating the appropriate offset based on its
        bounding box to ensure consistent alignment within the panel.

        Parameters
        ----------
        cap : Cap
            The cap object to be positioned.
        pos : build123d.Vector
            Target position for the cap placement.
        """
        bbox = cap.compound.bounding_box()
        offset = Vector(bbox.min.X, bbox.max.Y)
        cap.locate(Pos(pos - offset))
