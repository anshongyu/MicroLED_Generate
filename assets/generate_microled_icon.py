"""Generate the multi-resolution MicroLED application icon."""

from pathlib import Path

from PIL import Image, ImageDraw


SIZES = (16, 24, 32, 48, 64, 128, 256)
COLORS = (
    (239, 87, 87),
    (82, 211, 133),
    (79, 155, 246),
    (246, 197, 73),
)


def create_icon(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = max(1, round(size * 0.08))
    radius = max(2, round(size * 0.16))
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=radius,
        fill=(23, 34, 46, 255),
        outline=(88, 107, 123, 255),
        width=max(1, round(size * 0.025)),
    )

    grid = 5
    gap = max(1, round(size * 0.035))
    usable = size - 2 * margin
    cell = max(1, (usable - gap * (grid + 1)) // grid)
    grid_width = grid * cell + (grid - 1) * gap
    start = (size - grid_width) // 2
    corner = max(1, round(cell * 0.18))

    for row in range(grid):
        for column in range(grid):
            left = start + column * (cell + gap)
            top = start + row * (cell + gap)
            color = COLORS[(row + column) % len(COLORS)]
            if row == 2 and column == 2:
                color = (242, 246, 250)
            draw.rounded_rectangle(
                (left, top, left + cell, top + cell),
                radius=corner,
                fill=(*color, 255),
            )
    return image


def main() -> None:
    output = Path(__file__).with_name("microled.ico")
    icon = create_icon(256)
    icon.save(output, format="ICO", sizes=[(size, size) for size in SIZES])
    print(f"Created {output}")


if __name__ == "__main__":
    main()