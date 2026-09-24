"""Main window for configuring and exporting a MicroLED Lightbox."""

from pathlib import Path

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

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
)
from microled_lightbox.speos_gateway import GenerationProgress
from microled_lightbox.worker import GenerationWorker


DEFAULT_SPEOS_PATH = r"C:\Program Files\ANSYS Inc\v261\Optical Products\SPEOS_RPC"
MICROMETERS_PER_MILLIMETER = 1_000.0


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MicroLED Lightbox Generator")
        self.setMinimumSize(760, 720)
        self._thread: QThread | None = None
        self._worker: GenerationWorker | None = None

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(self._build_array_group())
        layout.addWidget(self._build_source_group(), 1)
        layout.addWidget(self._build_export_group())
        layout.addLayout(self._build_action_row())
        self.setCentralWidget(central)
        self._update_summary()

    def _build_array_group(self) -> QGroupBox:
        group = QGroupBox("Array")
        form = QGridLayout(group)
        self.x_count = QSpinBox()
        self.x_count.setRange(1, 300)
        self.x_count.setValue(10)
        self.y_count = QSpinBox()
        self.y_count.setRange(1, 150)
        self.y_count.setValue(10)
        self.pitch_x = _double_spin(0.001, 1_000_000.0, 40.0)
        self.pitch_y = _double_spin(0.001, 1_000_000.0, 40.0)
        self.flux_threshold = _double_spin(0.0, 1.0, 0.01)
        form.addWidget(QLabel("X source count"), 0, 0)
        form.addWidget(self.x_count, 0, 1)
        form.addWidget(QLabel("Y source count"), 0, 2)
        form.addWidget(self.y_count, 0, 3)
        form.addWidget(QLabel("X Pitch (µm)"), 1, 0)
        form.addWidget(self.pitch_x, 1, 1)
        form.addWidget(QLabel("Y Pitch (µm)"), 1, 2)
        form.addWidget(self.pitch_y, 1, 3)
        self.flux_map_file = QLineEdit()
        self.flux_map_file.textChanged.connect(self._update_flux_mode_for_map)
        form.addWidget(QLabel("Normalized flux map"), 2, 0)
        form.addWidget(
            self._file_picker(
                self.flux_map_file,
                "Flux map (*.csv *.png *.jpg *.jpeg *.bmp);;All files (*.*)",
            ),
            2,
            1,
            1,
            3,
        )
        form.addWidget(QLabel("Source threshold"), 3, 0)
        form.addWidget(self.flux_threshold, 3, 1)
        self.summary = QLabel()
        self.summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        form.addWidget(self.summary, 4, 0, 1, 4)
        for widget in (
            self.x_count,
            self.y_count,
            self.pitch_x,
            self.pitch_y,
            self.flux_threshold,
        ):
            widget.valueChanged.connect(self._update_summary)
        return group

    def _build_source_group(self) -> QGroupBox:
        group = QGroupBox("Source")
        layout = QVBoxLayout(group)
        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("Type"))
        self.source_type = QComboBox()
        self.source_type.addItems(["Surface Source", "Rayfile Source"])
        selector_row.addWidget(self.source_type, 1)
        layout.addLayout(selector_row)

        self.source_stack = QStackedWidget()
        self.source_stack.addWidget(self._build_surface_page())
        self.source_stack.addWidget(self._build_rayfile_page())
        self.source_type.currentIndexChanged.connect(self.source_stack.setCurrentIndex)
        layout.addWidget(self.source_stack)
        return group

    def _build_surface_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        dimensions = QFormLayout()
        self.surface_x = _double_spin(0.001, 1_000_000.0, 35.0)
        self.surface_y = _double_spin(0.001, 1_000_000.0, 35.0)
        dimensions.addRow("Rectangle X length (µm)", self.surface_x)
        dimensions.addRow("Rectangle Y length (µm)", self.surface_y)
        self.intensity_type = QComboBox()
        self.intensity_type.addItems(["Lambertian", "Library"])
        dimensions.addRow("Intensity", self.intensity_type)
        layout.addLayout(dimensions)

        self.intensity_stack = QStackedWidget()
        self.intensity_stack.addWidget(self._build_lambertian_page())
        self.intensity_stack.addWidget(self._build_library_page())
        self.intensity_type.currentIndexChanged.connect(self.intensity_stack.setCurrentIndex)
        layout.addWidget(self.intensity_stack)
        return page

    def _build_lambertian_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.lambert_flux = _double_spin(0.001, 1_000_000_000.0, 1.0)
        self.total_angle = _double_spin(0.001, 180.0, 180.0)
        self.lambert_spectrum = QLineEdit()
        form.addRow("Maximum luminous flux (lm/cell)", self.lambert_flux)
        form.addRow("Total angle (deg)", self.total_angle)
        form.addRow("Spectrum", self._file_picker(self.lambert_spectrum, "Spectrum file (*.*)"))
        return page

    def _build_library_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.intensity_file = QLineEdit()
        self.library_spectrum = QLineEdit()
        self.library_x_direction = QLineEdit("1, 0, 0")
        self.library_y_direction = QLineEdit("0, 1, 0")
        self.flux_from_intensity = QCheckBox("From intensity file")
        self.flux_from_intensity.setChecked(True)
        self.library_flux = _double_spin(0.001, 1_000_000_000.0, 1.0)
        self.library_flux.setEnabled(False)
        self.flux_from_intensity.toggled.connect(
            lambda checked: self.library_flux.setEnabled(not checked)
        )
        form.addRow("Intensity file", self._file_picker(self.intensity_file, "Intensity (*.ies *.ldt *.xmp);;All files (*.*)"))
        form.addRow("X direction", self.library_x_direction)
        form.addRow("Y direction", self.library_y_direction)
        form.addRow("Spectrum", self._file_picker(self.library_spectrum, "Spectrum file (*.*)"))
        form.addRow("Flux", self.flux_from_intensity)
        form.addRow("Maximum luminous flux (lm/cell)", self.library_flux)
        return page

    def _build_rayfile_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.ray_file = QLineEdit()
        self.flux_from_rayfile = QCheckBox("From ray file")
        self.flux_from_rayfile.setChecked(True)
        self.ray_flux = _double_spin(0.001, 1_000_000_000.0, 1.0)
        self.ray_flux.setEnabled(False)
        self.flux_from_rayfile.toggled.connect(lambda checked: self.ray_flux.setEnabled(not checked))
        self.x_direction = QLineEdit("1, 0, 0")
        self.y_direction = QLineEdit("0, 1, 0")
        form.addRow("Ray file", self._file_picker(self.ray_file, "Ray file (*.*)"))
        form.addRow("Flux", self.flux_from_rayfile)
        form.addRow("Maximum luminous flux (lm/cell)", self.ray_flux)
        form.addRow("X direction", self.x_direction)
        form.addRow("Y direction", self.y_direction)
        return page

    def _build_export_group(self) -> QGroupBox:
        group = QGroupBox("Speos and Export")
        form = QFormLayout(group)
        self.speos_path = QLineEdit(DEFAULT_SPEOS_PATH)
        self.export_directory = QLineEdit(str(Path.cwd()))
        self.lightbox_name = QLineEdit("MicroLED_Array")
        form.addRow("SPEOS_RPC", self._directory_picker(self.speos_path))
        form.addRow("Export directory", self._directory_picker(self.export_directory))
        form.addRow("Lightbox name", self.lightbox_name)
        return group

    def _build_action_row(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label = QLabel("Ready")
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_generation)
        self.generate_button = QPushButton("Generate Lightbox")
        self.generate_button.setDefault(True)
        self.generate_button.clicked.connect(self._start_generation)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.generate_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addLayout(buttons)
        return layout

    def _file_picker(self, line_edit: QLineEdit, file_filter: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton("Browse")
        button.clicked.connect(lambda: self._browse_file(line_edit, file_filter))
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return container

    def _directory_picker(self, line_edit: QLineEdit) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton("Browse")
        button.clicked.connect(lambda: self._browse_directory(line_edit))
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return container

    def _browse_file(self, target: QLineEdit, file_filter: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select file", target.text(), file_filter)
        if path:
            target.setText(path)

    def _browse_directory(self, target: QLineEdit) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select directory", target.text())
        if path:
            target.setText(path)

    def _update_summary(self) -> None:
        count = self.x_count.value() * self.y_count.value()
        extent_x = (self.x_count.value() - 1) * self.pitch_x.value()
        extent_y = (self.y_count.value() - 1) * self.pitch_y.value()
        self.summary.setText(f"{count:,} sources  |  Center span {extent_x:g} x {extent_y:g} µm")

    def _update_flux_mode_for_map(self, map_path: str) -> None:
        has_flux_map = bool(map_path.strip())
        self.flux_from_intensity.setEnabled(not has_flux_map)
        self.flux_from_rayfile.setEnabled(not has_flux_map)
        if has_flux_map:
            self.flux_from_intensity.setChecked(False)
            self.flux_from_rayfile.setChecked(False)
        self.library_flux.setEnabled(has_flux_map or not self.flux_from_intensity.isChecked())
        self.ray_flux.setEnabled(has_flux_map or not self.flux_from_rayfile.isChecked())

    def _collect_config(self, overwrite: bool = False) -> GenerationConfig:
        array = ArrayConfig(
            self.x_count.value(),
            self.y_count.value(),
            self.pitch_x.value() / MICROMETERS_PER_MILLIMETER,
            self.pitch_y.value() / MICROMETERS_PER_MILLIMETER,
            self.flux_threshold.value(),
        )
        flux_map = FluxMapConfig.load(Path(self.flux_map_file.text().strip()), array)
        source: SurfaceConfig | RayFileConfig
        if self.source_type.currentIndex() == 0:
            intensity: LambertianConfig | LibraryIntensityConfig
            if self.intensity_type.currentIndex() == 0:
                intensity = LambertianConfig(
                    self.lambert_flux.value(),
                    self.total_angle.value(),
                    Path(self.lambert_spectrum.text().strip()),
                )
            else:
                from_file = self.flux_from_intensity.isChecked()
                intensity = LibraryIntensityConfig(
                    Path(self.intensity_file.text().strip()),
                    Path(self.library_spectrum.text().strip()),
                    from_file,
                    None if from_file else self.library_flux.value(),
                    _parse_vector(self.library_x_direction.text(), "IES X direction"),
                    _parse_vector(self.library_y_direction.text(), "IES Y direction"),
                )
            source = SurfaceConfig(
                self.surface_x.value() / MICROMETERS_PER_MILLIMETER,
                self.surface_y.value() / MICROMETERS_PER_MILLIMETER,
                intensity,
            )
        else:
            from_file = self.flux_from_rayfile.isChecked()
            source = RayFileConfig(
                Path(self.ray_file.text().strip()),
                from_file,
                None if from_file else self.ray_flux.value(),
                _parse_vector(self.x_direction.text(), "X direction"),
                _parse_vector(self.y_direction.text(), "Y direction"),
            )
        return GenerationConfig(
            array=array,
            source=source,
            flux_map=flux_map,
            export=ExportConfig(
                Path(self.export_directory.text().strip()),
                self.lightbox_name.text().strip(),
                overwrite,
            ),
            speos=SpeosConfig(Path(self.speos_path.text().strip())),
        )

    def _start_generation(self) -> None:
        try:
            config = self._collect_config()
        except FileExistsError:
            answer = QMessageBox.question(
                self,
                "Overwrite file",
                "The target Lightbox already exists. Overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                config = self._collect_config(overwrite=True)
            except (ValueError, FileExistsError) as error:
                self._show_validation_error(error)
                return
        except ValueError as error:
            self._show_validation_error(error)
            return

        self._set_running(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Preparing generation")
        self._thread = QThread(self)
        self._worker = GenerationWorker(config)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.succeeded.connect(self._on_succeeded)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._thread_finished)
        self._thread.start()

    def _cancel_generation(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.cancel_button.setEnabled(False)
            self.status_label.setText("Cancellation will occur after the current Speos operation")

    def _on_progress(self, update: GenerationProgress) -> None:
        if update.stage == "build" and update.total:
            value = int(update.completed / update.total * 80)
        elif update.stage == "commit geometry":
            value = 80
        elif update.stage == "commit sources":
            value = 80 + int(update.completed / update.total * 10)
        elif update.stage == "commit":
            value = 90 if update.completed else 82
        elif update.stage == "export":
            value = 100 if update.completed else 95
        else:
            value = 1
        self.progress_bar.setValue(value)
        self.status_label.setText(update.message)

    def _on_succeeded(self, path: str) -> None:
        self.progress_bar.setValue(100)
        self.status_label.setText(f"Completed: {path}")
        QMessageBox.information(self, "Export complete", f"Lightbox exported:\n{path}")

    def _on_failed(self, message: str) -> None:
        self.status_label.setText("Generation failed")
        QMessageBox.critical(self, "Generation failed", message)

    def _on_cancelled(self) -> None:
        self.status_label.setText("Cancelled")

    def _thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._set_running(False)

    def _set_running(self, running: bool) -> None:
        self.generate_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.source_type.setEnabled(not running)

    def _show_validation_error(self, error: Exception) -> None:
        QMessageBox.warning(self, "Invalid configuration", str(error))

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._thread is not None and self._thread.isRunning():
            QMessageBox.information(
                self,
                "Generation in progress",
                "Cancel the task and wait for it to finish before closing the application.",
            )
            event.ignore()
            return
        event.accept()


def _double_spin(minimum: float, maximum: float, value: float) -> QDoubleSpinBox:
    widget = QDoubleSpinBox()
    widget.setDecimals(6)
    widget.setRange(minimum, maximum)
    widget.setValue(value)
    widget.setSingleStep(max(minimum, value / 10))
    return widget


def _parse_vector(text: str, label: str) -> tuple[float, float, float]:
    try:
        values = tuple(float(item.strip()) for item in text.split(","))
    except ValueError as error:
        raise ValueError(f"{label} must contain three comma-separated numbers.") from error
    if len(values) != 3:
        raise ValueError(f"{label} must contain three comma-separated numbers.")
    return values
