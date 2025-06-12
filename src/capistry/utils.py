"""
General-purpose utility functions.

This module provides a collection of utility functions for various tasks including
spatial point generation, matrix transformations, geometric calculations, and
object introspection utilities.
"""

import math
import random
from functools import cached_property, reduce
from itertools import islice, tee
from operator import mul
from typing import Any, Iterable

from build123d import Location, Shape


def spaced_points(
    n: int,
    tolerance: float = 0.0,
    start: float = 0.0,
    end: float = 1.0,
    rand: random.Random | None = None,
) -> list[float]:
    """
    Generate n points in an interval with minimum circular spacing constraint.

    Generates n points in the interval [start, end) such that each pair of points
    is at least `tolerance` apart when considering the interval as circular (i.e.,
    the end wraps around to the start). The points are distributed with random
    spacing beyond the minimum tolerance requirement.

    Parameters
    ----------
    n : int
        Number of points to generate. Must be positive.
    tolerance : float, optional
        Minimum distance between any two consecutive points in circular order,
        by default 0.0
    start : float, optional
        Start of the interval (inclusive), by default 0.0
    end : float, optional
        End of the interval (exclusive), by default 1.0
    rand : random.Random or None, optional
        Random generator instance for reproducible results. If None, uses the
        default random module, by default None

    Returns
    -------
    list[float]
        Sorted list of n points in [start, end] satisfying the spacing constraint.
        Points are ordered from smallest to largest value.

    Raises
    ------
    ValueError
        If n <= 0, or start >= end, or tolerance is too large to fit n points
        with the required spacing in the circular interval.

    Examples
    --------
    >>> points = spaced_points(5, tolerance=0.1, start=0, end=1)
    >>> len(points)
    5
    >>> all(0 <= p < 1 for p in points)
    True

    Notes
    -----
    The algorithm works by:
    1. Calculating the minimum total space needed (n * tolerance)
    2. Distributing the remaining space randomly among the n gaps
    3. Placing points starting from a random position on the circle
    4. Returning the points sorted within the [start, end) interval
    """
    if n <= 0:
        return []
    if start >= end:
        raise ValueError("start must be less than end")
    if n == 1:
        return [rand.uniform(start, end)]

    rand = rand or random
    length = end - start
    min_spacing = n * tolerance

    if min_spacing > length:
        raise ValueError("Tolerance too large for the number of points on the circular interval")

    surplus = length - min_spacing

    # Randomly split the leftover space into count parts
    rand_parts = [rand.random() for _ in range(n)]
    sum_parts = sum(rand_parts)

    if sum_parts == 0:
        gaps = [tolerance + surplus / n] * n
    else:
        gaps = [tolerance + (part / sum_parts) * surplus for part in rand_parts]

    # Random starting point on the circle
    start_point = rand.uniform(start, end)

    points = []
    current = start_point
    for gap in gaps:
        points.append(current)
        current = (current + gap - start) % length + start

    return points


def rotate_matrix(matrix: list[list[Any]], n: int = 1) -> list[list[Any]]:
    """
    Rotate a 2D matrix by n quarter-turns clockwise.

    Rotates the input matrix by n * 90 degrees clockwise. The rotation is
    performed in-place conceptually but returns a new matrix. Supports
    arbitrary integer values of n (negative values rotate counter-clockwise).

    Parameters
    ----------
    matrix : list[list[Any]]
        A 2D rectangular matrix (list of lists) where all rows have equal length.
        Must be non-empty.
    n : int, optional
        Number of 90-degree clockwise rotations to perform, by default 1.
        Negative values rotate counter-clockwise.

    Returns
    -------
    list[list[Any]]
        A new matrix representing the rotated input. The dimensions may change
        (rows become columns and vice versa) depending on the rotation.

    Raises
    ------
    ValueError
        If the matrix is empty or if rows have different lengths (non-rectangular).

    Examples
    --------
    Rotate a 2x3 matrix once (90 degrees clockwise):
    >>> matrix = [[1, 2, 3], [4, 5, 6]]
    >>> rotated = rotate_matrix(matrix, 1)
    >>> rotated
    [[4, 1], [5, 2], [6, 3]]

    Rotate twice (180 degrees):
    >>> rotate_matrix(matrix, 2)
    [[6, 5, 4], [3, 2, 1]]

    Counter-clockwise rotation:
    >>> rotate_matrix(matrix, -1)
    [[3, 6], [2, 5], [1, 4]]

    Notes
    -----
    The function uses modulo arithmetic to handle arbitrary rotation counts
    efficiently (n % 4). The rotation algorithms are optimized for each
    quarter-turn case using pattern matching.
    """
    if not matrix or any(len(row) != len(matrix[0]) for row in matrix):
        raise ValueError("Matrix must be non-empty and all rows must have the same length.")

    n %= 4
    rows, cols = len(matrix), len(matrix[0])

    match n:
        case 1:
            return [[matrix[rows - 1 - j][i] for j in range(rows)] for i in range(cols)]
        case 2:
            return [[matrix[rows - 1 - i][cols - 1 - j] for j in range(cols)] for i in range(rows)]
        case 3:
            return [[matrix[j][cols - 1 - i] for j in range(rows)] for i in range(cols)]
    return [row[:] for row in matrix]


def mirror_matrix(matrix: list[list[Any]], horizontal: bool = True) -> list[list[Any]]:
    """
    Mirror a 2D matrix along the horizontal or vertical axis.

    Creates a mirrored copy of the input matrix. Horizontal mirroring flips
    the matrix left-to-right (reversing each row), while vertical mirroring
    flips the matrix top-to-bottom (reversing the order of rows).

    Parameters
    ----------
    matrix : list[list[Any]]
        A 2D rectangular matrix (list of lists) where all rows have equal length.
        Must be non-empty.
    horizontal : bool, optional
        Direction of mirroring. If True, mirror horizontally (left-right flip).
        If False, mirror vertically (top-bottom flip), by default True.

    Returns
    -------
    list[list[Any]]
        A new matrix that is the mirrored version of the input matrix.
        Dimensions remain the same as the input.

    Raises
    ------
    ValueError
        If the matrix is empty or if rows have different lengths (non-rectangular).

    Examples
    --------
    Horizontal mirroring (left-right flip):
    >>> matrix = [[1, 2, 3], [4, 5, 6]]
    >>> mirror_matrix(matrix, horizontal=True)
    [[3, 2, 1], [6, 5, 4]]

    Vertical mirroring (top-bottom flip):
    >>> mirror_matrix(matrix, horizontal=False)
    [[4, 5, 6], [1, 2, 3]]

    Notes
    -----
    The function creates a new matrix without modifying the original.
    For horizontal mirroring, each row is reversed using slice notation [::-1].
    For vertical mirroring, the order of rows is reversed.
    """
    if not matrix or any(len(row) != len(matrix[0]) for row in matrix):
        raise ValueError("Matrix must be non-empty and all rows must have the same length.")

    if horizontal:
        return [row[::-1] for row in matrix]
    return matrix[::-1]


def gloc(node: Shape) -> Location:
    """
    Compute the global location of a Shape node by composing path locations.

    Calculates the cumulative transformation by multiplying all Location objects
    along the node's path hierarchy. This is useful in hierarchical geometric
    models where local transformations need to be combined to get world coordinates.

    Parameters
    ----------
    node : Shape
        A Shape object that has a `path` attribute containing a sequence of
        subnodes, each with a `location` attribute of type Location.

    Returns
    -------
    Location
        The composed (cumulative) Location representing the global transformation
        from the root to this node. If the path is empty, returns the identity Location.

    Examples
    --------
    >>> from build123d import Location, Shape
    >>> # Assuming node has a path with Location transformations
    >>> global_loc = gloc(my_shape_node)
    >>> print(global_loc)

    Notes
    -----
    This function uses functools.reduce with the multiplication operator to
    compose transformations. The composition starts with an identity Location()
    and multiplies each location in the path sequence from start to end.
    """
    return reduce(mul, (n.location for n in node.path), Location())


def always_split(iterable: Iterable, index: int = 1) -> tuple[Iterable, Iterable]:
    """
    Split an iterable at a given index into two lazy iterators.

    Divides the input iterable into two parts: the first containing elements
    up to (but not including) the specified index, and the second containing
    the remaining elements. Both returned iterators are lazy and will always
    be returned even if the original iterable is shorter than the split index.

    Parameters
    ----------
    iterable : Iterable
        The input iterable to split. Can be any iterable type (list, tuple,
        generator, etc.).
    index : int, optional
        The position at which to split the iterable, by default 1.
        Elements at positions 0 to index-1 go to the first iterator,
        elements from index onwards go to the second iterator.

    Returns
    -------
    tuple[Iterable, Iterable]
        A tuple containing two iterators:
        - First iterator: elements from position 0 to index-1
        - Second iterator: elements from position index onwards
        Both iterators may be empty if the split point is beyond the iterable length.

    Examples
    --------
    Split a list at index 3:
    >>> data = [1, 2, 3, 4, 5, 6]
    >>> first, second = always_split(data, 3)
    >>> list(first)
    [1, 2, 3]
    >>> list(second)
    [4, 5, 6]

    Split at index larger than iterable length:
    >>> first, second = always_split([1, 2], 5)
    >>> list(first)
    [1, 2]
    >>> list(second)
    []

    Default split at index 1:
    >>> head, tail = always_split([1, 2, 3, 4])
    >>> list(head)
    [1]
    >>> list(tail)
    [2, 3, 4]

    Notes
    -----
    This function uses itertools.tee to create two independent iterators from
    the input, then uses islice to partition them at the specified index.
    The iterators are lazy, meaning they don't consume the input until iterated over.

    Warning: Since tee is used, if one iterator is consumed much more than the
    other, memory usage may grow to store the unconsumed elements.
    """
    it1, it2 = tee(iterable)
    return islice(it1, index), islice(it2, index, None)


def is_zeroish(*values: float, abs_tol: float = 1e-10) -> bool:
    """
    Check if all provided float values are close to zero within tolerance.

    Tests whether all input values are approximately zero using absolute
    tolerance comparison. This is useful for floating-point comparisons
    where exact zero comparison is unreliable due to precision limitations.

    Parameters
    ----------
    *values : float
        One or more float values to test for near-zero condition.
        Must be numeric types that can be compared with math.isclose.
    abs_tol : float, optional
        The absolute tolerance for the zero comparison, by default 1e-10.
        Values with absolute value less than this threshold are considered zero.

    Returns
    -------
    bool
        True if ALL provided values are within abs_tol of zero, False otherwise.
        Returns True for empty input (vacuous truth).

    Notes
    -----
    This function uses math.isclose with rel_tol=0 and the specified abs_tol,
    effectively performing |value - 0| <= abs_tol for each value.
    """
    return all(math.isclose(v, 0.0, abs_tol=abs_tol) for v in values)


def clear_cached_properties(obj: Any) -> list[str]:
    """
    Clear all cached_property values from an object's instance dictionary.

    Removes all cached values for properties decorated with @cached_property
    from the object's __dict__, forcing them to be recalculated on next access.
    This is useful for invalidating cached computations when underlying data changes.

    Parameters
    ----------
    obj : Any
        The object instance whose cached properties should be cleared.
        Must be an instance of a class that may have cached_property decorators.

    Returns
    -------
    list[str]
        A list of attribute names that were cleared from the object's __dict__.
        Empty list if no cached properties were found or none were cached.
    """
    cleared = []
    for attr in dir(type(obj)):
        if isinstance(getattr(type(obj), attr, None), cached_property):
            if attr in obj.__dict__:
                cleared.append(attr)
                obj.__dict__.pop(attr, None)
    return cleared
