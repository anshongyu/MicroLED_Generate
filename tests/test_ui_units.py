import tempfile
import unittest
import csv
from pathlib import Path
from typing import ClassVar, cast

from PIL import Image
from PySide6.QtWidgets import QApplication

from microled_lightbox.ui.main_window import MainWindow
from microled_lightbox.models import SurfaceConfig


class UiUnitTests(unittest.TestCase):
    application: ClassVar[QApplication]

    @classmethod
    def setUpClass(cls) -> None:
        instance = QApplication.instance()
        cls.application = cast(QApplication, instance) if instance else QApplication([])

    def test_surface_lengths_and_pitches_are_displayed_in_micrometers(self) -> None:
        window = MainWindow()
        try:
            self.assertIn("µm", window.summary.text())
            self.assertEqual(window.pitch_x.value(), 40.0)
            self.assertEqual(window.pitch_y.value(), 40.0)
            self.assertEqual(window.surface_x.value(), 35.0)
            self.assertEqual(window.surface_y.value(), 35.0)
            self.assertEqual(window.flux_threshold.value(), 0.01)
            self.assertEqual(window.bit_depth.value(), 10)
            self.assertEqual(window.library_x_direction.text(), "1, 0, 0")
            self.assertEqual(window.library_y_direction.text(), "0, 1, 0")
        finally:
            window.close()

    def test_surface_lengths_and_pitches_convert_to_millimeters_for_speos(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spectrum_file = root / "spectrum.spectrum"
            flux_csv = root / "flux.csv"
            speos_directory = root / "SPEOS_RPC"
            spectrum_file.touch()
            with flux_csv.open("w", newline="", encoding="utf-8") as file:
                csv.writer(file).writerows(((255, 128), (0, 255)))
            speos_directory.mkdir()
            window = MainWindow()
            try:
                window.x_count.setValue(2)
                window.y_count.setValue(2)
                window.pitch_x.setValue(100.0)
                window.pitch_y.setValue(200.0)
                window.surface_x.setValue(50.0)
                window.surface_y.setValue(80.0)
                window.bit_depth.setValue(8)
                window.lambert_spectrum.setText(str(spectrum_file))
                window.flux_map_file.setText(str(flux_csv))
                window.export_directory.setText(str(root))
                window.speos_path.setText(str(speos_directory))

                config = window._collect_config()

                self.assertEqual(config.array.pitch_x, 0.1)
                self.assertEqual(config.array.pitch_y, 0.2)
                if not isinstance(config.source, SurfaceConfig):
                    self.fail("Expected a SurfaceConfig from the default Surface Source UI.")
                self.assertEqual(config.source.width_x, 0.05)
                self.assertEqual(config.source.length_y, 0.08)
                self.assertEqual(config.array.max_gray_code, 255)
                self.assertEqual(config.flux_map.enabled_source_count, 3)
            finally:
                window.close()

    def test_png_flux_map_is_collected_and_forces_manual_file_flux_modes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spectrum_file = root / "spectrum.spectrum"
            png_file = root / "flux.png"
            speos_directory = root / "SPEOS_RPC"
            spectrum_file.touch()
            Image.new("L", (2, 2), 255).save(png_file)
            speos_directory.mkdir()
            window = MainWindow()
            try:
                window.x_count.setValue(2)
                window.y_count.setValue(2)
                window.lambert_spectrum.setText(str(spectrum_file))
                window.flux_map_file.setText(str(png_file))
                window.export_directory.setText(str(root))
                window.speos_path.setText(str(speos_directory))

                config = window._collect_config()

                self.assertEqual(config.flux_map.input_file, png_file)
                self.assertEqual(config.flux_map.enabled_source_count, 4)
                self.assertFalse(window.flux_from_intensity.isEnabled())
                self.assertFalse(window.flux_from_rayfile.isEnabled())
            finally:
                window.close()


if __name__ == "__main__":
    unittest.main()