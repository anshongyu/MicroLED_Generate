# MicroLED Lightbox Generator

PySide6 application that creates a centered array of independent Ansys Speos Surface or Rayfile
sources and exports them in one `.SPEOSLightBox` file.

## Requirements

- Python 3.12
- Ansys Speos RPC Server 25.2 or later
- A valid Speos license
- `uv`

The default installation directory is:

```text
C:\Program Files\ANSYS Inc\v261\Optical Products\SPEOS_RPC
```

## Run

```powershell
uv sync
uv run python main.py
```

## Windows Executable

Create a compact, windowed executable with:

```powershell
.\build_exe.ps1 -Clean
```

The output is `dist\MicroLED-Lightbox-Generator.exe`. The executable excludes optional PyVista,
VTK, and scientific preview dependencies. Ansys Speos RPC Server and a valid license must still be
installed on the target machine.

The embedded icon is generated from `assets\generate_microled_icon.py` as a multi-resolution
MicroLED RGB pixel array.

Run the server-independent unit tests with:

```powershell
uv run python -m unittest discover -s tests -v
```

## Right-turn arrow CSV

Generate an 82-row by 246-column headerless CSV filled with `0` and `1023`, where `1023` forms an
upward-to-right-turn arrow:

```powershell
uv run python generate_right_turn_arrow_csv.py
```

The command writes `right_turn_arrow.csv` to the project root.

## Array convention

- X count is the number of columns; Y count is the number of rows.
- Pitch is the center-to-center spacing.
- The complete array is centered at global `(0, 0, 0)` in the XY plane.
- The top-left element has minimum X and maximum Y.
- Rows advance toward negative Y and columns advance toward positive X.
- Sources use zero-based names `X{row}Y{column}`. Row 5, column 6 is `X5Y6`.
- A manually entered luminous flux is the maximum flux of one cell, in lumens.

Surface rectangles use positive-Z triangle winding. Library and Rayfile orientations use their
normalized X and Y direction vectors, with Z calculated from their cross product.

## Flux Maps

Select a normalized flux map in the Array section. Headerless CSV and PNG, JPEG, or BMP bitmap
images are supported.
Map row `r` maps to source row `Xr` and map column `c` maps to source column `Yc`; its top-left
value maps to `X0Y0`.

- A CSV must be exactly `Y source count` rows by `X source count` columns, with values from `0`
	through `1`.
- A bitmap is converted to grayscale while ignoring any Alpha channel, then contrast-stretched
	across the full image so its darkest pixel is `0` and brightest pixel is `1`.
	Its width and height must each be at least the requested source count in that direction.
- Each bitmap grid partition contributes its normalized grayscale average as the cell value.
- For all map types, factors below the user-defined `Source threshold` (default `0.01`) are treated
	as `0`.
- A nonzero value creates the corresponding source and applies
	$\mathrm{flux}_{cell}=\mathrm{maximum\ flux}\times\mathrm{factor}_{r,c}$.
- `0` leaves the cell off: no face or source is created and nothing is written to the Lightbox.
- Map-controlled Library and Rayfile sources use manual maximum flux; flux-from-file is disabled.

## Scale note

The UI accepts up to 300 by 150 sources. This creates 45,000 independent Speos source templates
and, for Surface mode, 45,000 faces. Validate progressively on the target workstation before using
the maximum size. Building runs in a worker thread and can be cancelled between source creations;
the Speos commit itself cannot be interrupted.

`ansys-speos-core` 0.9.2 returns an incorrect path value from `LightBox.export()`. The application
does not use that return value and instead verifies the exact requested output file.
