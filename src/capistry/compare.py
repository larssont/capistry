"""
A flexible module for comparing objects with structured metrics and generating
rich comparison tables. This module provides abstract base classes and concrete
implementations for defining comparable objects and visualizing their differences.

Classes
-------
Comparable : ABC
    Protocol for objects that can be compared using metrics.
Metric : dataclass
    A single metric with computation function and optional unit.
MetricGroup : dataclass
    A group containing related metrics with ordering.
MetricLayout : dataclass
    Layout of all metrics for a comparable object.
TableRow : dataclass
    A table row with computed values from multiple objects.
TableSection : dataclass
    A table section with multiple rows.
BaseComparer : ABC
    Abstract base class for all comparers.
Comparer : BaseComparer
    Default rich comparison implementation with table output.

Examples
--------
>>> class MyObject(Comparable):
...     def __init__(self, value):
...         self.value = value
...
...     @property
...     def metrics(self):
...         return MetricLayout(
...             owner=self,
...             groups=(
...                 MetricGroup("Basic", (
...                     Metric("Value", lambda: self.value, "units"),
...                 )),
...             )
...         )
>>>
>>> obj1 = MyObject(10)
>>> obj2 = MyObject(20)
>>> comparer = Comparer(obj1, obj2)
>>> comparer.show()
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal as Dec
from functools import cached_property
from numbers import Number
from typing import Any, Callable, Self, TypeVar

from rich import box
from rich.align import Align
from rich.console import Console, RenderableType
from rich.table import Table as RichTable

T = TypeVar("T", bound="Comparable")


class Comparable(ABC):
    """
    Abstract class for objects that can be compared using metrics.

    This abstract base class defines the interface that objects must implement
    to be used with the comparison framework. Objects implementing it
    must provide a metrics property that returns their metric layout.

    Methods
    -------
    metrics : MetricLayout[Self]
        Return the metric layout for this object.

    Examples
    --------
    >>> class Temperature(Comparable):
    ...     def __init__(self, celsius):
    ...         self.celsius = celsius
    ...
    ...     @property
    ...     def metrics(self):
    ...         return MetricLayout(
    ...             owner=self,
    ...             groups=(
    ...                 MetricGroup("Temperature", (
    ...                     Metric("Celsius", lambda: self.celsius, "°C"),
    ...                     Metric("Fahrenheit", lambda: self.celsius * 9/5 + 32, "°F"),
    ...                 )),
    ...             )
    ...         )
    """

    @property
    @abstractmethod
    def metrics(self) -> "MetricLayout[Self]":
        """
        Return the metric layout for this object.

        Returns
        -------
        MetricLayout[Self]
            The metric layout containing all metric groups for this object.
        """


@dataclass(frozen=True, slots=True)
class Metric:
    """
    A single metric with a name, computation function, and optional unit.

    Represents an individual measurable property of an object that can be
    computed dynamically and optionally includes a unit of measurement.

    Parameters
    ----------
    name : str
        The display name of the metric.
    compute : Callable[[], Any]
        A callable that computes the metric value when invoked.
    unit : str or None, default=None
        Optional unit of measurement for the metric.
    """

    name: str
    compute: Callable[[], Any]
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class MetricGroup:
    """
    A group containing related metrics.

    Groups logically related metrics together with a title and optional ordering
    information for display purposes. Lower order values appear first in
    comparison tables.

    Parameters
    ----------
    title : str
        The title/header for this group of metrics.
    metrics : tuple[Metric, ...]
        Tuple of Metric objects belonging to this group.
    order : int, default=0
        Display order for this group. Lower values appear first.
    """

    title: str
    metrics: tuple[Metric, ...]
    order: int = 0

    @classmethod
    def from_comparables(cls, *comparables: Comparable) -> tuple["MetricGroup", ...]:
        """
        Collect and flatten all MetricGroups from the given components.

        Extracts all metric groups from multiple comparable objects and
        returns them as a flattened tuple, filtering out None values.

        Parameters
        ----------
        *comparables : Comparable
            Variable number of comparable objects to extract groups from.

        Returns
        -------
        tuple[MetricGroup, ...]
            Flattened tuple of all metric groups from the input objects.

        Examples
        --------
        >>> obj1 = SomeComparable()
        >>> obj2 = AnotherComparable()
        >>> groups = MetricGroup.from_comparables(obj1, obj2)
        """
        return tuple(
            group
            for comparable in comparables
            if comparable is not None
            for group in comparable.metrics.groups
        )


@dataclass(frozen=True, slots=True)
class MetricLayout[T]:
    """
    Layout of all metrics for a comparable object.

    Contains the complete metric structure for a comparable object, including
    the owner reference and all metric groups.

    Parameters
    ----------
    owner : T
        The object that owns this metric layout.
    groups : tuple[MetricGroup, ...]
        Tuple of metric groups belonging to the owner.
    """

    owner: T
    groups: tuple[MetricGroup, ...]


@dataclass(frozen=True, slots=True)
class TableRow:
    """
    A table row with computed values from multiple objects.

    Represents a single row in a comparison table, containing the metric name,
    computation functions for each comparable object, and optional unit.

    Parameters
    ----------
    name : str
        The name/label for this row.
    computes : tuple[Callable[[], Any] | None, ...]
        Tuple of computation functions, one per comparable object.
        None indicates the metric is missing for that object.
    unit : str or None, default=None
        Optional unit of measurement for this row's values.
    """

    name: str
    computes: tuple[Callable[[], Any] | None, ...]  # None for missing metrics
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class TableSection:
    """
    A table section with multiple rows.

    Groups related table rows together under a common title, corresponding
    to a MetricGroup in the comparison framework.

    Parameters
    ----------
    title : str
        The title/header for this section.
    rows : tuple[TableRow, ...]
        Tuple of table rows in this section.
    """

    title: str
    rows: tuple[TableRow, ...]


class BaseComparer[T](ABC):
    """
    Abstract base class for all comparers.

    Provides the core functionality for comparing multiple objects that
    implement the Comparable protocol. Builds comparison tables by aligning
    metrics across objects and handling missing metrics gracefully.

    Parameters
    ----------
    *comparables : T
        Variable number of comparable objects to compare.
        At least one object is required.

    Attributes
    ----------
    table : tuple[TableSection, ...]
        The comparison table sections.
    comparables : tuple[T, ...]
        The objects being compared.

    Raises
    ------
    ValueError
        If no comparable objects are provided.

    Examples
    --------
    >>> class MyComparer(BaseComparer):
    ...     pass  # Implement abstract methods
    >>> comparer = MyComparer(obj1, obj2, obj3)
    """

    def __init__(self, *comparables: T):
        if not comparables:
            raise ValueError("At least one comparable required")

        self._comparables = tuple(comparables)
        self._table = self._build_table()

    @property
    def table(self) -> tuple[TableSection, ...]:
        """
        The comparison table.

        Returns
        -------
        tuple[TableSection, ...]
            Tuple of table sections containing the comparison data.
        """
        return self._table

    @property
    def comparables(self) -> tuple[T, ...]:
        """
        The objects being compared.

        Returns
        -------
        tuple[T, ...]
            Tuple of comparable objects passed to the constructor.
        """
        return self._comparables

    @cached_property
    def _group_orders(self) -> dict[str, int]:
        """
        Map each group title to its minimum order found across comparables.

        For each group title that appears across multiple objects, uses the
        minimum order value found, defaulting to 0 if no explicit order found.

        Returns
        -------
        dict[str, int]
            Mapping from group title to minimum order value.
        """
        order_map: dict[str, int] = {}
        for c in self._comparables:
            for group in c.metrics.groups:
                current_order = order_map.get(group.title, 0)
                # Keep minimum order if multiple
                if group.order < current_order or group.title not in order_map:
                    order_map[group.title] = group.order
        return order_map

    @cached_property
    def _metrics_map(self) -> list[dict[tuple[str, str], Metric]]:
        """
        For each comparable, map (group_title, metric_name) → Metric.

        Creates a mapping structure that allows efficient lookup of metrics
        by group title and metric name for each comparable object.

        Returns
        -------
        list[dict[tuple[str, str], Metric]]
            List of dictionaries, one per comparable, mapping
            (group_title, metric_name) tuples to Metric objects.
        """
        metrics_map: list[dict[tuple[str, str], Metric]] = []
        for c in self._comparables:
            metric_map: dict[tuple[str, str], Metric] = {}
            for group in c.metrics.groups:
                for metric in group.metrics:
                    metric_map[(group.title, metric.name)] = metric
            metrics_map.append(metric_map)
        return metrics_map

    @cached_property
    def _group_titles(self) -> set[str]:
        """
        Collect all unique group titles across comparables.

        Returns
        -------
        set[str]
            Set of unique group titles found across all comparable objects.
        """
        titles: set[str] = set()
        for c in self._comparables:
            for group in c.metrics.groups:
                titles.add(group.title)
        return titles

    def _collect_metric_names_for_group(self, group_title: str) -> list[str]:
        """
        For a given group title, get all unique metric names across comparables.

        Preserves the order in which metric names are first encountered
        across the comparable objects.

        Parameters
        ----------
        group_title : str
            The group title to collect metric names for.

        Returns
        -------
        list[str]
            List of unique metric names in first-encountered order.
        """
        seen: set[str] = set()
        names: list[str] = []
        for metric_map in self._metrics_map:
            # Find keys for this group title
            for g_title, metric_name in metric_map.keys():
                if g_title == group_title and metric_name not in seen:
                    seen.add(metric_name)
                    names.append(metric_name)
        return names

    def _build_table(self) -> tuple[TableSection, ...]:
        """
        Build comparison table sections with rows.

        Constructs the complete comparison table by organizing metrics into
        sections, aligning metrics across objects, and handling missing metrics.
        Groups are sorted by order value, then alphabetically by title.

        Returns
        -------
        tuple[TableSection, ...]
            Complete table structure ready for display.
        """
        metric_maps = self._metrics_map
        group_orders = self._group_orders

        sections: list[TableSection] = []

        titles = sorted(self._group_titles, key=lambda title: (group_orders.get(title, 0), title))

        for title in titles:
            names = self._collect_metric_names_for_group(title)
            rows: list[TableRow] = []

            for name in names:
                computes: list[Callable[[], Any] | None] = []
                unit: str | None = None

                for metric_map in metric_maps:
                    metric = metric_map.get((title, name))
                    computes.append(metric.compute if metric else None)
                    unit = unit or (metric.unit if metric else None)

                rows.append(TableRow(name, tuple(computes), unit))
            sections.append(TableSection(title, tuple(rows)))

        return tuple(sections)


class Comparer(BaseComparer[T]):
    """
    Default rich comparison implementation with table output.

    Provides a complete implementation of the comparison framework with
    rich console output capabilities. Handles formatting, delta calculations,
    and visual presentation of comparison data.

    Parameters
    ----------
    *comparables : T
        Variable number of comparable objects to compare.
        At least one object is required.

    Examples
    --------
    >>> comparer = Comparer(car1, car2, car3)
    >>> comparer.show(precision=2, show_deltas=True)
    >>> rich_table = comparer.to_table(title="Vehicle Comparison")
    """

    def to_table(
        self, precision: int = 3, show_deltas: bool = True, title: str = "🔍 Comparison Table"
    ) -> RichTable:
        """
        Format comparison as a rich table.

        Creates a formatted Rich table suitable for console display, with
        optional delta calculations between consecutive values.

        Parameters
        ----------
        precision : int, default=3
            Number of decimal places for numeric values.
        show_deltas : bool, default=True
            Whether to show differences between consecutive values.
        title : str, default="🔍 Comparison Table"
            Title to display at the top of the table.

        Returns
        -------
        RichTable
            Formatted table ready for console display.

        Examples
        --------
        >>> table = comparer.to_table(precision=2, show_deltas=False)
        >>> console.print(table)
        """
        table = RichTable(title=title, box=box.SIMPLE_HEAVY)
        table.add_column("Metric", style="bold cyan", no_wrap=True)

        # Add columns for each comparable
        for obj in self._comparables:
            label = self._get_label(obj)
            table.add_column(label, style="bold white", justify="right")

        # Add rows
        for section in self.table:
            # Section header
            table.add_row(
                f"[bold magenta]{section.title}[/bold magenta]", *[""] * len(self._comparables)
            )

            # Rows in this section
            for row in section.rows:
                table_row: list[RenderableType] = [
                    f"{row.name} ({row.unit})" if row.unit else row.name
                ]
                prev_val = None

                for compute in row.computes:
                    if compute is None:
                        # Missing metric
                        formatted = "[dim]-[/dim]"
                    else:
                        val = compute()
                        if show_deltas and prev_val is not None:
                            delta_str = self._format_delta(val, prev_val, precision)
                        else:
                            delta_str = ""

                        formatted = delta_str + self._format_value(val, precision)
                        prev_val = val

                    table_row.append(Align.right(formatted))

                table.add_row(*table_row)

        return table

    def show(
        self,
        precision: int = 3,
        show_deltas: bool = True,
        title: str = "🔍 Comparison Table",
        console: Console | None = None,
    ) -> None:
        """
        Print the comparison table to console.

        Displays the formatted comparison table directly to the console
        using Rich's console output capabilities.

        Parameters
        ----------
        precision : int, default=3
            Number of decimal places for numeric values.
        show_deltas : bool, default=True
            Whether to show differences between consecutive values.
        title : str, default="🔍 Comparison Table"
            Title to display above the table.
        console : Console or None, default=None
            Rich Console instance to use. If None, creates a new one.

        Examples
        --------
        >>> comparer.show()
        >>> comparer.show(precision=1, show_deltas=False, title="My Comparison")
        >>> comparer.show(console=my_console)
        """
        console = console or Console()
        table = self.to_table(precision=precision, show_deltas=show_deltas, title=title)
        console.print(table)

    def _get_label(self, obj: T) -> str:
        """
        Get a display label for an object.

        Attempts to find a suitable display label by checking for common
        attributes like 'name' or 'label', falling back to string representation.

        Parameters
        ----------
        obj : T
            The object to get a label for.

        Returns
        -------
        str
            Display label for the object.
        """
        for attr in ("name", "label"):
            if hasattr(obj, attr):
                val = getattr(obj, attr)
                if callable(val):
                    try:
                        result = val()
                        if isinstance(result, str) and result:
                            return result
                    except Exception:
                        continue
                if isinstance(val, str) and val:
                    return val
        return str(obj)

    def _format_value(self, val: Any, precision: int) -> str:
        """
        Format a value for display.

        Applies appropriate formatting rules based on the value type,
        with special handling for booleans, numbers, sequences, and None.

        Parameters
        ----------
        val : Any
            The value to format.
        precision : int
            Number of decimal places for numeric values.

        Returns
        -------
        str
            Formatted string representation of the value.
        """
        if isinstance(val, bool):
            return "✔" if val else "✖"
        elif isinstance(val, Number):
            return str(round(Dec(str(val)), precision))
        elif isinstance(val, (list, tuple)):
            return ", ".join(str(v) for v in val)
        elif val is None:
            return "-"
        return str(val)

    def _format_delta(self, current: Any, previous: Any, precision: int) -> str:
        """
        Format the difference between two values.

        Calculates and formats the delta between consecutive values,
        with color coding for positive (green) and negative (red) changes.

        Parameters
        ----------
        current : Any
            The current value.
        previous : Any
            The previous value to compare against.
        precision : int
            Number of decimal places for the delta value.

        Returns
        -------
        str
            Formatted delta string with color markup, or empty string
            if delta cannot be calculated or is zero.
        """
        try:
            delta = current - previous
            if not isinstance(delta, int | float | Dec):
                raise TypeError
            if delta == 0:
                return ""

            rounded = round(Dec(str(abs(delta))), precision)
            sign = "+" if delta > 0 else "-"
            color = "green" if delta > 0 else "red"
            return f"[{color}]{sign}{rounded}[/{color}] "
        except TypeError:
            pass
        return ""
