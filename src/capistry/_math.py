"""
Geometry utilities for mathematical computations.

This module provides functions for calculating properties of geometric shapes
including regular polygons, circles, and 3D shapes like prisms and cylinders.
It includes utilities for finding divisors of integers and computing dimensions,
areas, and surface areas of various geometric objects.

Functions
---------
divisors : function
    Find all divisors of a positive integer.
polygon_width : function
    Calculate horizontal width of a regular polygon.
polygon_height : function
    Calculate vertical height of a regular polygon.
polygon_area : function
    Calculate area of a regular polygon.
polygon_prism_surface : function
    Calculate surface area of a regular polygon prism.
cylinder_surface : function
    Calculate surface area of a cylinder.
circle_area : function
    Calculate area of a circle.
"""

from math import cos, pi, sin, tan


def divisors(n):
    """
    Find all divisors of a positive integer in ascending order.

    Parameters
    ----------
    n : int
        A positive integer for which to find divisors.

    Returns
    -------
    list of int
        All divisors of n in ascending order.

    Raises
    ------
    ValueError
        If n is not a positive integer (n <= 0).

    Examples
    --------
    >>> divisors(12)
    [1, 2, 3, 4, 6, 12]
    >>> divisors(7)
    [1, 7]
    >>> divisors(1)
    [1]
    """
    if n <= 0:
        raise ValueError("Input must be a positive integer.")

    small_divisors = []
    big_divisors = []

    for i in range(1, int(n**0.5) + 1):
        if n % i == 0:
            small_divisors.append(i)
            if i != n // i:
                big_divisors.append(n // i)

    return small_divisors + big_divisors[::-1]


def polygon_width(n, radius, inradius=True):
    """
    Calculate the horizontal width of a regular polygon.

    Computes the horizontal width (bounding box width) of a regular polygon
    with one side aligned flat at the bottom.

    Parameters
    ----------
    n : int
        Number of sides of the polygon. Must be >= 3.
    radius : float
        The radius value. Interpreted as inradius if `inradius` is True,
        otherwise as circumradius.
    inradius : bool, optional
        Whether the given radius is the inradius (True) or
        circumradius (False). Default is True.

    Returns
    -------
    float
        The horizontal width of the polygon's bounding box.

    Raises
    ------
    ValueError
        If n < 3 (polygon must have at least 3 sides).
    """
    if n < 3:
        raise ValueError("Polygon must have at least 3 sides.")

    angle = pi / n
    r = radius / cos(angle) if inradius else radius
    rotation = -pi / 2 + angle

    x_coords = [r * cos(2 * pi * k / n + rotation) for k in range(n)]
    return max(x_coords) - min(x_coords)


def polygon_height(n, radius, inradius=True):
    """
    Calculate the vertical height of a regular polygon.

    Computes the vertical height of a regular polygon with one side
    aligned horizontally at the bottom.

    Parameters
    ----------
    n : int
        Number of sides of the polygon. Must be >= 3.
    radius : float
        The radius value. Interpreted as inradius if `inradius` is True,
        otherwise as circumradius.
    inradius : bool, optional
        Whether the given radius is the inradius (True) or
        circumradius (False). Default is True.

    Returns
    -------
    float
        The vertical height from the flat bottom side to the topmost point.

    Raises
    ------
    ValueError
        If n < 3 (polygon must have at least 3 sides).

    Notes
    -----
    For even-sided polygons, the height is twice the inradius.
    For odd-sided polygons, the height is the sum of inradius and circumradius.
    """
    if n < 3:
        raise ValueError("Polygon must have at least 3 sides.")

    actual_inradius = radius if inradius else radius * cos(pi / n)

    if n % 2 == 0:
        return 2 * actual_inradius
    else:
        circumradius = radius / cos(pi / n) if inradius else radius
        return actual_inradius + circumradius


def polygon_area(n, radius, inradius=False):
    """
    Calculate the area of a regular polygon.

    Parameters
    ----------
    n : int
        Number of sides of the polygon. Must be >= 3.
    radius : float
        The radius value. Interpreted as inradius if `inradius` is True,
        otherwise as circumradius.
    inradius : bool, optional
        Whether the given radius is the inradius (True) or
        circumradius (False). Default is False.

    Returns
    -------
    float
        The area of the regular polygon.

    Raises
    ------
    ValueError
        If n < 3 (polygon must have at least 3 sides).
    """
    if n < 3:
        raise ValueError("Polygon must have at least 3 sides.")

    if inradius:
        return n * radius**2 * tan(pi / n)
    return (n / 2) * radius**2 * sin(2 * pi / n)


def polygon_prism_surface(n, radius, height, inradius=False):
    """
    Calculate the surface area of a regular polygon prism.

    Computes the total surface area including both bases and lateral faces
    of a prism with regular polygon cross-section.

    Parameters
    ----------
    n : int
        Number of sides of the polygon base. Must be >= 3.
    radius : float
        The radius value. Interpreted as inradius if `inradius` is True,
        otherwise as circumradius.
    height : float
        Height of the prism.
    inradius : bool, optional
        Whether the given radius is the inradius (True) or
        circumradius (False). Default is False.

    Returns
    -------
    float
        The total surface area of the polygon prism.

    Raises
    ------
    ValueError
        If n < 3 (polygon must have at least 3 sides).
    """
    if n < 3:
        raise ValueError("Polygon must have at least 3 sides.")

    base_area = polygon_area(n, radius, inradius)
    side_length = 2 * radius * tan(pi / n) if inradius else 2 * radius * sin(pi / n)
    perimeter = n * side_length

    return 2 * base_area + perimeter * height


def cylinder_surface(radius, height):
    """
    Calculate the surface area of a cylinder.

    Computes the total surface area including both circular bases and
    the lateral surface.

    Parameters
    ----------
    radius : float
        Radius of the cylinder base.
    height : float
        Height of the cylinder.

    Returns
    -------
    float
        The total surface area of the cylinder.
    """
    return 2 * pi * radius * (radius + height)


def circle_area(radius):
    """
    Calculate the area of a circle.

    Parameters
    ----------
    radius : float
        Radius of the circle.

    Returns
    -------
    float
        The area of the circle.
    """
    return pi * radius**2
