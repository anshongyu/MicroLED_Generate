"""Validated configuration models shared by the UI and Speos gateway."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from microled_lightbox.flux_map import BITMAP_SUFFIXES, FluxMap, load_bitmap_flux_map, load_flux_map
from microled_lightbox.layout import Vector3, rayfile_axis_system


class SourceKind(str, Enum):
    SURFACE = "surface"
    RAYFILE = "rayfile"


class SurfaceIntensityKind(str, Enum):
    LAMBERTIAN = "lambertian"
    LIBRARY = "library"


@dataclass(frozen=True, slots=True)
class SpeosConfig:
    install_path: Path = Path(
        r"C:\Program Files\ANSYS Inc\v261\Optical Products\SPEOS_RPC"
    )
    version: str = "261"
    message_size_bytes: int = 256 * 1024**2

    def __post_init__(self) -> None:
        if not self.install_path.is_dir():
            raise ValueError(f"Speos RPC directory does not exist: {self.install_path}")
        if self.message_size_bytes < 4 * 1024**2:
            raise ValueError("Speos message size must be at least 4 MB.")


@dataclass(frozen=True, slots=True)
class ArrayConfig:
    x_count: int
    y_count: int
    pitch_x: float
    pitch_y: float
    flux_threshold: float = 0.01
    bit_depth: int = 10

    def __post_init__(self) -> None:
        if not 1 <= self.x_count <= 500:
            raise ValueError("X source count must be between 1 and 500.")
        if not 1 <= self.y_count <= 500:
            raise ValueError("Y source count must be between 1 and 500.")
        if self.pitch_x <= 0 or self.pitch_y <= 0:
            raise ValueError("X and Y pitches must be greater than 0.")
        if not 0.0 <= self.flux_threshold <= 1.0:
            raise ValueError("Source threshold must be between 0 and 1.")
        if not 1 <= self.bit_depth <= 16:
            raise ValueError("MicroLED bit depth must be between 1 and 16.")

    @property
    def source_count(self) -> int:
        return self.x_count * self.y_count

    @property
    def max_gray_code(self) -> int:
        return (1 << self.bit_depth) - 1


@dataclass(frozen=True, slots=True)
class FluxMapConfig:
    """Discrete per-cell MicroLED grayscale codes loaded from a CSV or bitmap."""

    input_file: Path
    matrix: FluxMap
    max_gray_code: int

    @classmethod
    def load(cls, input_file: Path, array: ArrayConfig) -> "FluxMapConfig":
        suffix = input_file.suffix.lower()
        if suffix == ".csv":
            matrix = load_flux_map(
                input_file, array.y_count, array.x_count, array.max_gray_code
            )
        elif suffix in BITMAP_SUFFIXES:
            matrix = load_bitmap_flux_map(
                input_file,
                array.y_count,
                array.x_count,
                array.max_gray_code,
            )
        else:
            raise ValueError("Grayscale map must be a CSV, PNG, JPEG, or BMP file.")
        return cls(
            input_file=input_file,
            matrix=_apply_source_threshold(matrix, array.flux_threshold, array.max_gray_code),
            max_gray_code=array.max_gray_code,
        )

    @property
    def enabled_source_count(self) -> int:
        return sum(value > 0 for row in self.matrix for value in row)

    def factor_for(self, row: int, column: int) -> float:
        return self.code_for(row, column) / self.max_gray_code

    def code_for(self, row: int, column: int) -> int:
        return self.matrix[row][column]


def _apply_source_threshold(matrix: FluxMap, threshold: float, max_gray_code: int) -> FluxMap:
    return tuple(
        tuple(0 if value / max_gray_code < threshold else value for value in row)
        for row in matrix
    )


@dataclass(frozen=True, slots=True)
class LambertianConfig:
    luminous_flux_lm: float
    total_angle_deg: float
    spectrum_file: Path

    def __post_init__(self) -> None:
        _require_positive(self.luminous_flux_lm, "Luminous flux")
        _validate_angle(self.total_angle_deg)
        _require_file(self.spectrum_file, "Spectrum file")


@dataclass(frozen=True, slots=True)
class LibraryIntensityConfig:
    intensity_file: Path
    spectrum_file: Path
    flux_from_intensity_file: bool
    luminous_flux_lm: float | None = None
    x_direction: Vector3 = (1.0, 0.0, 0.0)
    y_direction: Vector3 = (0.0, 1.0, 0.0)

    def __post_init__(self) -> None:
        _require_file(self.intensity_file, "Intensity file")
        _require_file(self.spectrum_file, "Spectrum file")
        _validate_optional_flux(
            from_file=self.flux_from_intensity_file,
            luminous_flux_lm=self.luminous_flux_lm,
            source_label="intensity file",
        )
        rayfile_axis_system((0.0, 0.0, 0.0), self.x_direction, self.y_direction)


@dataclass(frozen=True, slots=True)
class SurfaceConfig:
    width_x: float
    length_y: float
    intensity: LambertianConfig | LibraryIntensityConfig

    def __post_init__(self) -> None:
        _require_positive(self.width_x, "Surface X length")
        _require_positive(self.length_y, "Surface Y length")

    @property
    def intensity_kind(self) -> SurfaceIntensityKind:
        if isinstance(self.intensity, LambertianConfig):
            return SurfaceIntensityKind.LAMBERTIAN
        return SurfaceIntensityKind.LIBRARY


@dataclass(frozen=True, slots=True)
class RayFileConfig:
    ray_file: Path
    flux_from_ray_file: bool
    luminous_flux_lm: float | None = None
    x_direction: Vector3 = (1.0, 0.0, 0.0)
    y_direction: Vector3 = (0.0, 1.0, 0.0)

    def __post_init__(self) -> None:
        _require_file(self.ray_file, "Ray file")
        _validate_optional_flux(
            from_file=self.flux_from_ray_file,
            luminous_flux_lm=self.luminous_flux_lm,
            source_label="ray file",
        )
        rayfile_axis_system((0.0, 0.0, 0.0), self.x_direction, self.y_direction)


@dataclass(frozen=True, slots=True)
class ExportConfig:
    directory: Path
    lightbox_name: str
    overwrite: bool = False

    def __post_init__(self) -> None:
        if not self.lightbox_name.strip():
            raise ValueError("Lightbox name is required.")
        if Path(self.lightbox_name).name != self.lightbox_name:
            raise ValueError("Lightbox name must not contain a directory path.")
        if not self.directory.is_dir():
            raise ValueError(f"Export directory does not exist: {self.directory}")
        if self.output_path.exists() and not self.overwrite:
            raise FileExistsError(f"Output file already exists: {self.output_path}")

    @property
    def normalized_name(self) -> str:
        suffix = ".SPEOSLightBox"
        if self.lightbox_name.lower().endswith(suffix.lower()):
            return self.lightbox_name[: -len(suffix)] + suffix
        return self.lightbox_name + suffix

    @property
    def feature_name(self) -> str:
        return Path(self.normalized_name).stem

    @property
    def output_path(self) -> Path:
        return self.directory / self.normalized_name


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    array: ArrayConfig
    source: SurfaceConfig | RayFileConfig
    flux_map: FluxMapConfig
    export: ExportConfig
    speos: SpeosConfig

    def __post_init__(self) -> None:
        if self.flux_map.enabled_source_count == 0:
            raise ValueError("Grayscale map contains no enabled cells.")
        if isinstance(self.source, SurfaceConfig):
            intensity = self.source.intensity
            if isinstance(intensity, LibraryIntensityConfig) and intensity.flux_from_intensity_file:
                raise ValueError("Grayscale maps require manual luminous flux for Library intensity.")
        elif self.source.flux_from_ray_file:
            raise ValueError("Grayscale maps require manual luminous flux for Rayfile sources.")

    @property
    def source_kind(self) -> SourceKind:
        if isinstance(self.source, SurfaceConfig):
            return SourceKind.SURFACE
        return SourceKind.RAYFILE


def _require_positive(value: float, label: str) -> None:
    if value <= 0:
        raise ValueError(f"{label} must be greater than 0.")


def _validate_angle(value: float) -> None:
    if not 0 < value <= 180:
        raise ValueError("Total angle must be greater than 0 and at most 180 degrees.")


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {path}")


def _validate_optional_flux(
    *,
    from_file: bool,
    luminous_flux_lm: float | None,
    source_label: str,
) -> None:
    if from_file:
        return
    if luminous_flux_lm is None:
        raise ValueError(f"Luminous flux is required when flux is not read from the {source_label}.")
    _require_positive(luminous_flux_lm, "Luminous flux")
