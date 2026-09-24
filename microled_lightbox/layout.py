"""Deterministic geometry and naming for a centered MicroLED array."""

from dataclasses import dataclass
from math import isclose, sqrt
from typing import Iterator, Sequence


Vector3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class ArrayElement:
    """Position and identity of one array element."""

    row: int
    column: int
    name: str
    center: Vector3


@dataclass(frozen=True, slots=True)
class RectangleMesh:
    """A rectangular emitting face represented by two triangles."""

    vertices: tuple[float, ...]
    normals: tuple[float, ...] = (0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0)
    facets: tuple[int, ...] = (0, 1, 2, 0, 2, 3)


def iter_array_elements(
    x_count: int,
    y_count: int,
    pitch_x: float,
    pitch_y: float,
) -> Iterator[ArrayElement]:
    """Yield elements from top-left, row by row, around the global origin."""
    if x_count < 1 or y_count < 1:
        raise ValueError("Array counts must be at least 1.")
    if pitch_x <= 0 or pitch_y <= 0:
        raise ValueError("Array pitches must be greater than 0.")

    x_offset = (x_count - 1) / 2
    y_offset = (y_count - 1) / 2
    for row in range(y_count):
        center_y = (y_offset - row) * pitch_y
        for column in range(x_count):
            center_x = (column - x_offset) * pitch_x
            yield ArrayElement(
                row=row,
                column=column,
                name=f"X{row}Y{column}",
                center=(center_x, center_y, 0.0),
            )


def rectangle_mesh(center: Vector3, width_x: float, length_y: float) -> RectangleMesh:
    """Create an XY rectangle whose triangle winding points toward positive Z."""
    if width_x <= 0 or length_y <= 0:
        raise ValueError("Surface dimensions must be greater than 0.")

    center_x, center_y, center_z = center
    half_x = width_x / 2
    half_y = length_y / 2
    return RectangleMesh(
        vertices=(
            center_x - half_x,
            center_y - half_y,
            center_z,
            center_x + half_x,
            center_y - half_y,
            center_z,
            center_x + half_x,
            center_y + half_y,
            center_z,
            center_x - half_x,
            center_y + half_y,
            center_z,
        )
    )


def rayfile_axis_system(
    origin: Vector3,
    x_direction: Sequence[float],
    y_direction: Sequence[float],
) -> tuple[float, ...]:
    """Build the Speos 12-value axis system from orthogonal X and Y vectors."""
    x_axis = _normalize(x_direction, "X")
    y_axis = _normalize(y_direction, "Y")
    dot_product = sum(x_value * y_value for x_value, y_value in zip(x_axis, y_axis))
    if not isclose(dot_product, 0.0, abs_tol=1e-9):
        raise ValueError("X and Y direction vectors must be orthogonal.")

    z_axis = (
        x_axis[1] * y_axis[2] - x_axis[2] * y_axis[1],
        x_axis[2] * y_axis[0] - x_axis[0] * y_axis[2],
        x_axis[0] * y_axis[1] - x_axis[1] * y_axis[0],
    )
    return (*origin, *x_axis, *y_axis, *z_axis)


def _normalize(values: Sequence[float], label: str) -> Vector3:
    if len(values) != 3:
        raise ValueError(f"{label} direction must have exactly 3 components.")
    vector = tuple(float(value) for value in values)
    magnitude = sqrt(sum(value * value for value in vector))
    if isclose(magnitude, 0.0, abs_tol=1e-12):
        raise ValueError(f"{label} direction must be nonzero.")
    return tuple(value / magnitude for value in vector)  # type: ignore[return-value]
