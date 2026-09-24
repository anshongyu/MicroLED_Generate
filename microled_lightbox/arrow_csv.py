"""Create a fixed-size right-turn arrow CSV matrix with 0/1023 values."""

import csv
from pathlib import Path


ROWS = 82
COLUMNS = 246
ACTIVE_VALUE = 1023

_CURVE_CENTER_COLUMN = 100
_CURVE_CENTER_ROW = 48
_CURVE_INNER_RADIUS = 26
_CURVE_OUTER_RADIUS = 38


def build_right_turn_arrow() -> tuple[tuple[int, ...], ...]:
    """Return an 82-by-246 0/1023 matrix with an upward-to-right arrow."""
    return tuple(
        tuple(
            ACTIVE_VALUE if _is_arrow_cell(row, column) else 0
            for column in range(COLUMNS)
        )
        for row in range(ROWS)
    )


def write_right_turn_arrow_csv(output_path: Path) -> Path:
    """Write the 0/1023 arrow matrix to ``output_path`` without a header."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        csv.writer(file).writerows(build_right_turn_arrow())
    return output_path


def _is_arrow_cell(row: int, column: int) -> bool:
    return (
        _is_vertical_shaft(row, column)
        or _is_turn(row, column)
        or _is_horizontal_shaft(row, column)
        or _is_arrow_head(row, column)
    )


def _is_vertical_shaft(row: int, column: int) -> bool:
    return 48 <= row <= 76 and 62 <= column <= 74


def _is_turn(row: int, column: int) -> bool:
    horizontal_distance = column - _CURVE_CENTER_COLUMN
    vertical_distance = row - _CURVE_CENTER_ROW
    squared_distance = horizontal_distance**2 + vertical_distance**2
    return (
        column <= _CURVE_CENTER_COLUMN
        and row <= _CURVE_CENTER_ROW
        and _CURVE_INNER_RADIUS**2 <= squared_distance <= _CURVE_OUTER_RADIUS**2
    )


def _is_horizontal_shaft(row: int, column: int) -> bool:
    return 10 <= row <= 22 and 100 <= column <= 204


def _is_arrow_head(row: int, column: int) -> bool:
    return 204 <= column <= 236 and abs(row - 16) <= (236 - column) // 2