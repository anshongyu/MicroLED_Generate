"""Adapter that turns validated MicroLED settings into a Speos Lightbox."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ansys.speos.core import Project  # type: ignore[import-untyped]
from ansys.speos.core.launcher import (  # type: ignore[import-untyped]
    launch_local_speos_rpc_server,
)
from ansys.speos.core.source import SourceRayFile, SourceSurface  # type: ignore[import-untyped]
import ansys.speos.core.generic.general_methods as speos_general_methods  # type: ignore[import-untyped]
from ansys.speos.core.generic.parameters import (  # type: ignore[import-untyped]
    OptPropParameters,
    SopMirrorParameters,
)

from microled_lightbox.layout import iter_array_elements, rayfile_axis_system, rectangle_mesh
from microled_lightbox.models import (
    GenerationConfig,
    LambertianConfig,
    LibraryIntensityConfig,
    RayFileConfig,
    SurfaceConfig,
)


CancelCheck = Callable[[], bool]
ProgressCallback = Callable[["GenerationProgress"], None]


class Commitable(Protocol):
    """Feature with the public Speos commit operation used by this gateway."""

    def commit(self) -> object: ...


@dataclass(frozen=True, slots=True)
class GenerationProgress:
    stage: str
    completed: int
    total: int
    message: str


class GenerationCancelled(RuntimeError):
    """Raised when generation is cancelled between Speos operations."""


class SpeosGateway:
    """Create one Lightbox containing a centered array of independent sources."""

    def __init__(
        self,
        launcher: Callable[..., Any] = launch_local_speos_rpc_server,
        project_factory: Callable[..., Any] = Project,
    ) -> None:
        self._launcher = launcher
        self._project_factory = project_factory

    def generate(
        self,
        config: GenerationConfig,
        progress: ProgressCallback | None = None,
        is_cancelled: CancelCheck | None = None,
    ) -> Path:
        report = progress or (lambda update: None)
        cancelled = is_cancelled or (lambda: False)
        output_path = config.export.output_path

        report(GenerationProgress("connect", 0, 1, "Starting Speos RPC server"))
        speos = self._launcher(
            version=config.speos.version,
            speos_rpc_path=config.speos.install_path,
            server_message_size=config.speos.message_size_bytes,
            client_message_size=config.speos.message_size_bytes,
        )
        graphics_available = speos_general_methods._GRAPHICS_AVAILABLE
        # The application exports Lightboxes and never requests PyVista source previews.
        # Avoid creating three VTK arrows per source during array construction.
        speos_general_methods._GRAPHICS_AVAILABLE = False
        try:
            parent_project = self._project_factory(speos=speos)
            lightbox = parent_project.create_lightbox(config.export.feature_name)
            elements = iter_array_elements(
                config.array.x_count,
                config.array.y_count,
                config.array.pitch_x,
                config.array.pitch_y,
            )

            if isinstance(config.source, SurfaceConfig):
                root_part, surface_sources, active_faces = self._build_surface_array(
                    lightbox,
                    elements,
                    config.source,
                    config.flux_map,
                    report,
                    cancelled,
                )
                self._commit_surface_geometry(root_part, report)
                self._commit_absorber_property(lightbox, active_faces, report)
                self._commit_surface_sources(lightbox, surface_sources, report, cancelled)
            elif self._requires_lightbox_commit(type(config.source)):
                self._build_rayfile_array(
                    lightbox,
                    elements,
                    config.source,
                    config.flux_map,
                    report,
                    cancelled,
                )
                self._raise_if_cancelled(cancelled)
                report(
                    GenerationProgress(
                        "commit",
                        0,
                        1,
                        "Committing the Lightbox; this operation cannot be interrupted",
                    )
                )
                lightbox.commit()
                report(GenerationProgress("commit", 1, 1, "Lightbox committed"))

            self._raise_if_cancelled(cancelled)
            report(GenerationProgress("export", 0, 1, f"Exporting {output_path.name}"))
            lightbox.export(output_path)
            if not output_path.exists():
                raise RuntimeError(f"Speos did not create the requested export: {output_path}")
            report(GenerationProgress("export", 1, 1, f"Exported {output_path}"))
            return output_path
        finally:
            try:
                speos.close()
            finally:
                speos_general_methods._GRAPHICS_AVAILABLE = graphics_available

    def _build_surface_array(
        self,
        lightbox,
        elements,
        config: SurfaceConfig,
        flux_map,
        report: ProgressCallback,
        cancelled: CancelCheck,
    ) -> tuple[Commitable, list[SourceSurface], list[object]]:
        root_part = lightbox.create_root_part()
        body = root_part.create_body("MicroLEDArray")
        faces_by_code: dict[int, list[object]] = {}
        active_faces: list[object] = []
        sources: list[SourceSurface] = []
        completed = 0
        for element in elements:
            self._raise_if_cancelled(cancelled)
            gray_code = flux_map.code_for(element.row, element.column)
            if gray_code == 0:
                continue
            face = body.create_face(f"Emitter_{element.name}")
            mesh = rectangle_mesh(element.center, config.width_x, config.length_y)
            face.vertices = list(mesh.vertices)
            face.normals = list(mesh.normals)
            face.facets = list(mesh.facets)

            faces_by_code.setdefault(gray_code, []).append(face)
            active_faces.append(face)
            completed += 1
            self._report_element_progress(
                report, "build", completed, flux_map.enabled_source_count
            )

        total_groups = len(faces_by_code)
        for completed, (gray_code, faces) in enumerate(sorted(faces_by_code.items()), start=1):
            self._raise_if_cancelled(cancelled)
            source = lightbox.create_source(f"Gray{gray_code}", feature_type=SourceSurface)
            source.set_exitance_constant().geometries = [(face, False) for face in faces]
            _configure_surface_source(
                source,
                config,
                gray_code / flux_map.max_gray_code * len(faces),
            )
            sources.append(source)
            self._report_element_progress(report, "create grayscale sources", completed, total_groups)
        return root_part, sources, active_faces

    @staticmethod
    def _commit_surface_geometry(root_part: Commitable, report: ProgressCallback) -> None:
        report(
            GenerationProgress(
                "commit geometry",
                0,
                1,
                "Committing Surface geometry; this operation cannot be interrupted",
            )
        )
        root_part.commit()
        report(GenerationProgress("commit geometry", 1, 1, "Surface geometry committed"))

    @staticmethod
    def _commit_absorber_property(lightbox, faces: Sequence[object], report: ProgressCallback) -> None:
        report(GenerationProgress("commit absorber", 0, 1, "Creating absorbing optical property"))
        absorber = lightbox.create_optical_property(
            "Absorber",
            parameters=OptPropParameters(sop_parameters=SopMirrorParameters(reflectance=0)),
        )
        absorber.geometries = faces
        absorber.commit()
        report(GenerationProgress("commit absorber", 1, 1, "Absorbing optical property committed"))

    def _commit_surface_sources(
        self,
        lightbox,
        sources: list[SourceSurface],
        report: ProgressCallback,
        cancelled: CancelCheck,
    ) -> None:
        total = len(sources)
        for completed, source in enumerate(sources, start=1):
            self._raise_if_cancelled(cancelled)
            source.intensity.commit()
            source._source_template.surface.intensity_guid = source.intensity.intensity_template_link.key
            self._report_element_progress(report, "commit intensity templates", completed, total)

        self._raise_if_cancelled(cancelled)
        report(
            GenerationProgress(
                "commit sources",
                0,
                1,
                "Committing Surface sources in one scene update; this operation cannot be interrupted",
            )
        )
        lightbox.project.commit()
        report(GenerationProgress("commit sources", 1, 1, "Surface sources committed"))

    def _build_rayfile_array(
        self,
        lightbox,
        elements,
        config: RayFileConfig,
        flux_map,
        report: ProgressCallback,
        cancelled: CancelCheck,
    ) -> None:
        completed = 0
        for element in elements:
            self._raise_if_cancelled(cancelled)
            flux_factor = flux_map.factor_for(element.row, element.column)
            if flux_factor == 0.0:
                continue
            source = lightbox.create_source(element.name, feature_type=SourceRayFile)
            source.ray_file_uri = config.ray_file
            source.axis_system = list(
                rayfile_axis_system(element.center, config.x_direction, config.y_direction)
            )
            _configure_rayfile_source(source, config, flux_factor)
            completed += 1
            self._report_element_progress(
                report, "build", completed, flux_map.enabled_source_count
            )

    @staticmethod
    def _report_element_progress(
        report: ProgressCallback, stage: str, completed: int, total: int
    ) -> None:
        if completed == 1 or completed == total or completed % 100 == 0:
            report(
                GenerationProgress(stage, completed, total, f"Created {completed} of {total} sources")
            )

    @staticmethod
    def _requires_lightbox_commit(source_type: type[SurfaceConfig] | type[RayFileConfig]) -> bool:
        """Rayfile sources rely on the project-level batch scene commit."""
        return source_type is RayFileConfig

    @staticmethod
    def _raise_if_cancelled(cancelled: CancelCheck) -> None:
        if cancelled():
            raise GenerationCancelled("Generation cancelled by user.")


def _configure_surface_source(source, config: SurfaceConfig, flux_factor: float = 1.0) -> None:
    intensity_config = config.intensity
    source.spectrum.set_library().file_uri = intensity_config.spectrum_file

    if isinstance(intensity_config, LambertianConfig):
        source.flux.set_luminous()
        source.flux.value = intensity_config.luminous_flux_lm * flux_factor
        cosine = source.intensity.set_cos()
        cosine.n = 1
        cosine.total_angle = intensity_config.total_angle_deg
        return

    if not isinstance(intensity_config, LibraryIntensityConfig):
        raise TypeError(f"Unsupported surface intensity configuration: {type(intensity_config)}")
    if intensity_config.flux_from_intensity_file:
        source.set_flux_from_intensity_file()
    else:
        if intensity_config.luminous_flux_lm is None:
            raise ValueError("Library intensity requires maximum luminous flux.")
        source.flux.set_luminous()
        source.flux.value = intensity_config.luminous_flux_lm * flux_factor
    library = source.intensity.set_library()
    library.intensity_file_uri = intensity_config.intensity_file
    library.orientation_axis_system = list(
        rayfile_axis_system(
            (0.0, 0.0, 0.0),
            intensity_config.x_direction,
            intensity_config.y_direction,
        )
    )


def _configure_rayfile_source(source, config: RayFileConfig, flux_factor: float = 1.0) -> None:
    if config.flux_from_ray_file:
        source.set_flux_from_ray_file()
    else:
        if config.luminous_flux_lm is None:
            raise ValueError("Rayfile source requires maximum luminous flux.")
        source.flux.set_luminous()
        source.flux.value = config.luminous_flux_lm * flux_factor