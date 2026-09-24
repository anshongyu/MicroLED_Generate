import tempfile
import unittest
from pathlib import Path
import csv

from PIL import Image

from microled_lightbox.models import (
    ArrayConfig,
    ExportConfig,
    FluxMapConfig,
    GenerationConfig,
    LambertianConfig,
    LibraryIntensityConfig,
    RayFileConfig,
    SpeosConfig,
    SurfaceConfig,
    SurfaceIntensityKind,
)


class ConfigModelTests(unittest.TestCase):
    def test_array_limits_and_source_count(self) -> None:
        config = ArrayConfig(x_count=300, y_count=150, pitch_x=0.1, pitch_y=0.2)

        self.assertEqual(config.source_count, 45_000)
        with self.assertRaises(ValueError):
            ArrayConfig(x_count=501, y_count=1, pitch_x=1.0, pitch_y=1.0)
        with self.assertRaises(ValueError):
            ArrayConfig(x_count=1, y_count=1, pitch_x=1.0, pitch_y=1.0, flux_threshold=1.1)

    def test_flux_map_loads_normalized_values_and_counts_enabled_cells(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            csv_file = Path(directory) / "flux.csv"
            with csv_file.open("w", newline="", encoding="utf-8") as file:
                csv.writer(file).writerows(((1.0, 0.5), (0.0, 0.25)))

            flux_map = FluxMapConfig.load(csv_file, ArrayConfig(2, 2, 1.0, 1.0))

            self.assertEqual(flux_map.factor_for(0, 1), 0.5)
            self.assertEqual(flux_map.enabled_source_count, 3)

    def test_flux_map_rejects_invalid_shape_and_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            csv_file = Path(directory) / "flux.csv"
            csv_file.write_text("1,0.5,0\n", encoding="utf-8")
            array = ArrayConfig(2, 2, 1.0, 1.0)
            with self.assertRaises(ValueError):
                FluxMapConfig.load(csv_file, array)

    def test_csv_flux_map_uses_configurable_source_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            csv_file = Path(directory) / "flux.csv"
            csv_file.write_text("0.05,0.2\n", encoding="utf-8")

            kept = FluxMapConfig.load(csv_file, ArrayConfig(2, 1, 1.0, 1.0, 0.01))
            skipped = FluxMapConfig.load(csv_file, ArrayConfig(2, 1, 1.0, 1.0, 0.1))

            self.assertEqual(kept.matrix, ((0.05, 0.2),))
            self.assertEqual(skipped.matrix, ((0.0, 0.2),))

    def test_png_flux_map_stretches_contrast_and_averages_grid_cells(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            png_file = Path(directory) / "flux.png"
            image = Image.new("L", (4, 2))
            image.putdata((10, 10, 110, 110, 10, 10, 60, 60))
            image.save(png_file)

            flux_map = FluxMapConfig.load(png_file, ArrayConfig(2, 1, 1.0, 1.0))

            self.assertEqual(flux_map.matrix[0][0], 0.0)
            self.assertAlmostEqual(flux_map.matrix[0][1], 0.75)

    def test_png_flux_map_ignores_alpha_when_computing_grayscale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            png_file = Path(directory) / "flux.png"
            image = Image.new("RGBA", (2, 1), (255, 255, 255, 0))
            image.putpixel((1, 0), (0, 0, 0, 255))
            image.save(png_file)

            flux_map = FluxMapConfig.load(png_file, ArrayConfig(2, 1, 1.0, 1.0))

            self.assertEqual(flux_map.matrix, ((1.0, 0.0),))

    def test_png_flux_map_rejects_images_smaller_than_grid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            png_file = Path(directory) / "flux.png"
            Image.new("L", (1, 1), 255).save(png_file)

            with self.assertRaises(ValueError):
                FluxMapConfig.load(png_file, ArrayConfig(2, 1, 1.0, 1.0))

    def test_jpeg_and_bmp_flux_maps_use_the_bitmap_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = Image.new("L", (2, 1))
            image.putdata((0, 255))
            for suffix in (".jpg", ".bmp"):
                bitmap_file = root / f"flux{suffix}"
                image.save(bitmap_file)

                flux_map = FluxMapConfig.load(bitmap_file, ArrayConfig(2, 1, 1.0, 1.0))

                self.assertEqual(flux_map.matrix[0][0], 0.0)
                self.assertAlmostEqual(flux_map.matrix[0][1], 1.0, places=2)

    def test_png_flux_map_maps_constant_nonblack_images_to_full_power(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            png_file = Path(directory) / "flux.png"
            Image.new("L", (2, 2), 80).save(png_file)

            flux_map = FluxMapConfig.load(png_file, ArrayConfig(2, 2, 1.0, 1.0))

            self.assertEqual(flux_map.matrix, ((1.0, 1.0), (1.0, 1.0)))

    def test_png_flux_map_thresholds_low_partition_averages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            png_file = Path(directory) / "flux.png"
            image = Image.new("L", (202, 1), 0)
            image.putpixel((0, 0), 255)
            image.save(png_file)

            flux_map = FluxMapConfig.load(png_file, ArrayConfig(2, 1, 1.0, 1.0))

            self.assertEqual(flux_map.matrix, ((0.0, 0.0),))

    def test_png_flux_map_uses_configurable_source_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            png_file = Path(directory) / "flux.png"
            image = Image.new("L", (3, 1), 0)
            image.putpixel((1, 0), 51)
            image.putpixel((2, 0), 255)
            image.save(png_file)

            kept = FluxMapConfig.load(png_file, ArrayConfig(3, 1, 1.0, 1.0, 0.1))
            skipped = FluxMapConfig.load(png_file, ArrayConfig(3, 1, 1.0, 1.0, 0.3))

            self.assertAlmostEqual(kept.matrix[0][1], 0.2)
            self.assertEqual(skipped.matrix[0][1], 0.0)

    def test_flux_map_requires_manual_rayfile_flux(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ray_file = root / "source.ray"
            csv_file = root / "flux.csv"
            rpc_directory = root / "SPEOS_RPC"
            ray_file.touch()
            csv_file.write_text("1\n", encoding="utf-8")
            rpc_directory.mkdir()
            array = ArrayConfig(1, 1, 1.0, 1.0)

            with self.assertRaises(ValueError):
                GenerationConfig(
                    array=array,
                    source=RayFileConfig(ray_file, True),
                    flux_map=FluxMapConfig.load(csv_file, array),
                    export=ExportConfig(root, "array"),
                    speos=SpeosConfig(rpc_directory),
                )

            csv_file.write_text("1,1.1\n0,0\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                FluxMapConfig.load(csv_file, array)

    def test_surface_modes_validate_real_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            spectrum = Path(directory) / "spectrum.spectrum"
            intensity = Path(directory) / "distribution.ies"
            spectrum.touch()
            intensity.touch()

            lambertian = SurfaceConfig(
                width_x=0.1,
                length_y=0.2,
                intensity=LambertianConfig(1.5, 120.0, spectrum),
            )
            library = SurfaceConfig(
                width_x=0.1,
                length_y=0.2,
                intensity=LibraryIntensityConfig(intensity, spectrum, True),
            )

            self.assertEqual(lambertian.intensity_kind, SurfaceIntensityKind.LAMBERTIAN)
            self.assertEqual(library.intensity_kind, SurfaceIntensityKind.LIBRARY)

    def test_manual_library_flux_is_required_and_positive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            spectrum = Path(directory) / "spectrum.spectrum"
            intensity = Path(directory) / "distribution.ies"
            spectrum.touch()
            intensity.touch()

            with self.assertRaises(ValueError):
                LibraryIntensityConfig(intensity, spectrum, False)
            with self.assertRaises(ValueError):
                LibraryIntensityConfig(intensity, spectrum, False, 0.0)

    def test_library_intensity_rejects_nonorthogonal_orientation_axes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            spectrum = Path(directory) / "spectrum.spectrum"
            intensity = Path(directory) / "distribution.ies"
            spectrum.touch()
            intensity.touch()

            with self.assertRaises(ValueError):
                LibraryIntensityConfig(
                    intensity,
                    spectrum,
                    True,
                    x_direction=(1.0, 0.0, 0.0),
                    y_direction=(1.0, 1.0, 0.0),
                )

    def test_rayfile_validates_flux_and_axes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ray_file = Path(directory) / "source.ray"
            ray_file.touch()

            RayFileConfig(ray_file, True)
            RayFileConfig(ray_file, False, 2.0)
            with self.assertRaises(ValueError):
                RayFileConfig(ray_file, False)
            with self.assertRaises(ValueError):
                RayFileConfig(ray_file, True, x_direction=(1, 0, 0), y_direction=(1, 1, 0))

    def test_export_path_is_normalized_and_protected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            export = ExportConfig(Path(directory), "array")

            self.assertEqual(export.normalized_name, "array.SPEOSLightBox")
            self.assertEqual(export.feature_name, "array")
            export.output_path.touch()
            with self.assertRaises(FileExistsError):
                ExportConfig(Path(directory), "array")


if __name__ == "__main__":
    unittest.main()