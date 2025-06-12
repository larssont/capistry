"""
Taper modeling for four-sided directional values.

This module defines the Taper class, which models taper values on four sides—
front, back, left, and right. The module provides utilities for creating uniform
tapers, scaling values, clamping to ranges, and exposing metrics for
comparison or visualization.

Classes
-------
Taper
    Represents a directional taper with methods for transformation and metrics.
"""

from dataclasses import dataclass
from typing import Self

from capistry.compare import Comparable, Metric, MetricGroup, MetricLayout


@dataclass
class Taper(Comparable):
    """
    Represents a four-sided directional taper with transformation utilities.

    The class provides methods for creating uniform tapers, scaling all values
    proportionally, clamping values to safe ranges, and exposing values through
    a metrics system for comparison.

    Parameters
    ----------
    front : float, default=0.0
        Taper value for the front side
    back : float, default=0.0
        Taper value for the back side
    left : float, default=0.0
        Taper value for the left side
    right : float, default=0.0
        Taper value for the right side

    Examples
    --------
    Create a taper with individual side values:
    >>> taper = Taper(front=2.5, back=1.0, left=0.5, right=0.8)
    >>> print(taper)
    Taper (2.50, 1.00, 0.50, 0.80)

    Create a uniform taper:
    >>> uniform_taper = Taper.uniform(1.5)
    >>> print(uniform_taper)
    Taper (1.50, 1.50, 1.50, 1.50)

    Scale an existing taper:
    >>> scaled = taper.scaled(2.0)
    >>> print(scaled)
    Taper (5.00, 2.00, 1.00, 1.60)

    Clamp values to a safe range:
    >>> clamped = taper.clamp(0.0, 3.0)
    >>> print(clamped)
    Taper (2.50, 1.00, 0.50, 0.80)

    Notes
    -----
    The Taper class inherits from Comparable, enabling comparison operations
    and integration with metric systems. All transformation methods return
    new instances rather than modifying the original taper in-place.

    Units are not enforced by the class itself - they depend on the application
    context.
    """

    front: float = 0.0
    back: float = 0.0
    left: float = 0.0
    right: float = 0.0

    @classmethod
    def uniform(cls, value: float) -> Self:
        """
        Create a taper with all sides set to the same value.

        This is a convenience constructor for creating symmetric tapers where
        all four sides have identical taper values. Commonly used for uniform
        draft angles in manufacturing or symmetric scaling operations.

        Parameters
        ----------
        value : float
            The taper value to apply to all four sides (front, back, left, right).

        Returns
        -------
        Taper
            A new Taper instance with all sides set to the specified value.

        Notes
        -----
        This method is equivalent to calling Taper(value, value, value, value)
        but provides clearer intent.
        """
        return cls(front=value, back=value, left=value, right=value)

    def scaled(self, factor: float) -> "Taper":
        """
        Return a new Taper instance with all values scaled by a factor.

        Multiplies each taper value (front, back, left, right) by the given
        scaling factor.

        Parameters
        ----------
        factor : float
            The scaling factor to apply to all taper values. Values greater
            than 1.0 increase the taper, values between 0.0 and 1.0 decrease
            the taper, and negative values reverse the taper direction.

        Returns
        -------
        Taper
            A new Taper instance with all values multiplied by the factor.
            The original instance is unchanged.

        Examples
        --------
        Double all taper values:
        >>> original = Taper(front=1.0, back=2.0, left=0.5, right=1.5)
        >>> doubled = original.scaled(2.0)
        >>> print(doubled)
        Taper (2.00, 4.00, 1.00, 3.00)

        Notes
        -----
        This method creates a new instance and does not modify the original
        taper. The scaling is applied independently to each side.
        """
        return Taper(
            front=self.front * factor,
            back=self.back * factor,
            left=self.left * factor,
            right=self.right * factor,
        )

    def clamp(self, min_value: float, max_value: float) -> "Taper":
        """
        Clamp all taper values to the specified range.

        Constrains each taper value to lie within [min_value, max_value] by
        setting values below `min_value` to `min_value` and values above `max_value`
        to `max_value`. This is useful for enforcing manufacturing constraints,
        safety limits, or valid parameter ranges.

        Parameters
        ----------
        min_value : float
            The minimum allowed value for any taper side. Values below this
            threshold will be set to min_value.
        max_value : float
            The maximum allowed value for any taper side. Values above this
            threshold will be set to max_value.

        Returns
        -------
        Taper
            A new Taper instance with all values clamped to the specified range.
            The original instance is unchanged.

        Raises
        ------
        ValueError
            If min_value > max_value (invalid range).

        Examples
        --------
        Clamp to symmetric range:
        >>> extreme_taper = Taper(front=-10.0, back=10.0, left=0.0, right=5.0)
        >>> balanced = extreme_taper.clamp(-3.0, 3.0)
        >>> print(balanced)
        Taper (-3.00, 3.00, 0.00, 3.00)

        Notes
        -----
        This method applies the standard clamping operation:
        min(max(value, min_value), max_value) to each taper side independently.
        """
        if min_value > max_value:
            raise ValueError(f"min_value ({min_value}) must be <= max_value ({max_value})")

        return Taper(
            front=min(max(self.front, min_value), max_value),
            back=min(max(self.back, min_value), max_value),
            left=min(max(self.left, min_value), max_value),
            right=min(max(self.right, min_value), max_value),
        )

    @property
    def metrics(self) -> MetricLayout[Self]:
        """
        Expose taper values through the `capistry.Comparable` system for comparison.

        Provides a structured interface for accessing taper values through
        the `capistry.Comparable` system.

        Returns
        -------
        MetricLayout
            A metric layout containing a single "Taper" group with four metrics
            representing the front, back, left, and right taper values.
        """
        return MetricLayout(
            owner=self,
            groups=(
                MetricGroup(
                    "Taper",
                    (
                        Metric("Front", lambda: self.front, "°"),
                        Metric("Back", lambda: self.back, "°"),
                        Metric("Left", lambda: self.left, "°"),
                        Metric("Right", lambda: self.right, "°"),
                    ),
                ),
            ),
        )

    def __str__(self) -> str:
        """
        Format the class name and taper values to 2 decimal places.

        Returns
        -------
        str
            String like "ClassName (front, back, left, right)".
        """
        return (
            f"{type(self).__name__} "
            f"({self.front:.2f}, {self.back:.2f}, {self.left:.2f}, {self.right:.2f})"
        )
