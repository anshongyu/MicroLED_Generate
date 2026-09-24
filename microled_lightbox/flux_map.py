"""Parse normalized per-cell luminous-flux maps from CSV and bitmap image files."""

import csv
from pathlib import Path

from PIL import Image


FluxMap = tuple[tuple[float, ...], ...]
PNG_THRESHOLD = 0.01
BITMAP_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp"}


def load_flux_map(csv_file: Path, expected_rows: int, expected_columns: int) -> FluxMap:
    """Load a headerless CSV whose rows map to X indices and columns to Y indices."""
    if not csv_file.is_file():
        raise ValueError(f"Flux CSV does not exist: {csv_file}")

    rows: list[tuple[float, ...]] = []
    try:
        with csv_file.open(newline="", encoding="utf-8-sig") as file:
            for row_number, raw_row in enumerate(csv.reader(file), start=1):
                if not raw_row or not any(value.strip() for value in raw_row):
                    continue
                if len(raw_row) != expected_columns:
                    raise ValueError(
                        f"Flux CSV row {row_number} has {len(raw_row)} columns; "
                        f"expected {expected_columns}."
                    )
                try:
                    row = tuple(float(value.strip()) for value in raw_row)
                except ValueError as error:
                    raise ValueError(f"Flux CSV row {row_number} contains a non-numeric value.") from error
                if any(not 0.0 <= value <= 1.0 for value in row):
                    raise ValueError(
                        f"Flux CSV row {row_number} must contain normalized values from 0 to 1."
                    )
                rows.append(row)
    except OSError as error:
        raise ValueError(f"Unable to read flux CSV: {csv_file}") from error

    if len(rows) != expected_rows:
        raise ValueError(f"Flux CSV has {len(rows)} rows; expected {expected_rows}.")
    return tuple(rows)


def load_bitmap_flux_map(
    bitmap_file: Path,
    expected_rows: int,
    expected_columns: int,
    threshold: float = PNG_THRESHOLD,
) -> FluxMap:
    """Convert a bitmap image into normalized mean flux factors for an array grid."""
    if not bitmap_file.is_file():
        raise ValueError(f"Flux bitmap does not exist: {bitmap_file}")

    try:
        source_image: Image.Image = Image.open(bitmap_file)
    except OSError as error:
        raise ValueError(f"Unable to read flux bitmap: {bitmap_file}") from error
    try:
        grayscale = source_image.convert("RGB").convert("L")
        width, height = grayscale.size
        if width < expected_columns or height < expected_rows:
            raise ValueError(
                f"Flux bitmap size {width}x{height} is smaller than the required "
                f"array grid {expected_columns}x{expected_rows}."
            )
        normalized_pixels = _normalize_pixels(tuple(grayscale.tobytes()))
    finally:
        source_image.close()

    rows: list[tuple[float, ...]] = []
    for row in range(expected_rows):
        top = row * height // expected_rows
        bottom = (row + 1) * height // expected_rows
        values: list[float] = []
        for column in range(expected_columns):
            left = column * width // expected_columns
            right = (column + 1) * width // expected_columns
            total = 0.0
            for pixel_row in range(top, bottom):
                offset = pixel_row * width
                total += sum(normalized_pixels[offset + left : offset + right])
            factor = total / ((bottom - top) * (right - left))
            values.append(0.0 if factor < threshold else factor)
        rows.append(tuple(values))
    return tuple(rows)


def load_png_flux_map(
    png_file: Path,
    expected_rows: int,
    expected_columns: int,
    threshold: float = PNG_THRESHOLD,
) -> FluxMap:
    """Backward-compatible PNG alias for :func:`load_bitmap_flux_map`."""
    return load_bitmap_flux_map(png_file, expected_rows, expected_columns, threshold)


def _normalize_pixels(pixels: tuple[int, ...]) -> tuple[float, ...]:
    minimum = min(pixels)
    maximum = max(pixels)
    if minimum == maximum:
        return tuple(0.0 if minimum == 0 else 1.0 for _ in pixels)
    span = maximum - minimum
    return tuple((value - minimum) / span for value in pixels)