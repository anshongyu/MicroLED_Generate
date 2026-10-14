import tempfile
import unittest
from collections.abc import Callable
import csv
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

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
from microled_lightbox.speos_gateway import (
    GenerationCancelled,
    GenerationProgress,
    SpeosGateway,
    _configure_rayfile_source,
    _configure_surface_source,
)
from microled_lightbox.layout import iter_array_elements
import microled_lightbox.speos_gateway as speos_gateway


def make_source() -> SimpleNamespace:
    flux = SimpleNamespace(set_luminous=Mock(), value=None)
    spectrum_library = SimpleNamespace(file_uri=None)
    spectrum = SimpleNamespace(set_library=Mock(return_value=spectrum_library))
    cosine = SimpleNamespace(n=None, total_angle=None)
    library = SimpleNamespace(
        intensity_file_uri=None,
        orientation_axis_system=None,
    )
    intensity = SimpleNamespace(
        set_cos=Mock(return_value=cosine),
        set_library=Mock(return_value=library),
    )
    return SimpleNamespace(
        flux=flux,
        spectrum=spectrum,
        intensity=intensity,
        set_flux_from_intensity_file=Mock(),
        set_flux_from_ray_file=Mock(),
        cosine=cosine,
        intensity_library=library,
    )


class SourceConfigurationTests(unittest.TestCase):
    def test_lambertian_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            spectrum = Path(directory) / "spectrum.spectrum"
            spectrum.touch()
            source = make_source()
            config = SurfaceConfig(1.0, 1.0, LambertianConfig(2.5, 120.0, spectrum))

            _configure_surface_source(source, config)

            source.flux.set_luminous.assert_called_once_with()
            self.assertEqual(source.flux.value, 2.5)
            self.assertEqual(source.cosine.n, 1)
            self.assertEqual(source.cosine.total_angle, 120.0)
            self.assertEqual(source.spectrum.set_library.return_value.file_uri, spectrum)

    def test_library_configuration_uses_file_flux_and_configured_axes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            spectrum = Path(directory) / "spectrum.spectrum"
            intensity = Path(directory) / "distribution.ies"
            spectrum.touch()
            intensity.touch()
            source = make_source()
            config = SurfaceConfig(
                1.0,
                1.0,
                LibraryIntensityConfig(intensity, spectrum, True),
            )

            _configure_surface_source(source, config)

            source.set_flux_from_intensity_file.assert_called_once_with()
            self.assertEqual(source.intensity_library.intensity_file_uri, intensity)
            self.assertEqual(
                source.intensity_library.orientation_axis_system,
                [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
            )

    def test_rayfile_manual_flux_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ray_file = Path(directory) / "source.ray"
            ray_file.touch()
            source = make_source()

            _configure_rayfile_source(source, RayFileConfig(ray_file, False, 4.0))

            source.flux.set_luminous.assert_called_once_with()
            self.assertEqual(source.flux.value, 4.0)

    def test_cancellation_is_reported(self) -> None:
        with self.assertRaises(GenerationCancelled):
            SpeosGateway._raise_if_cancelled(lambda: True)


class GatewayOrchestrationTests(unittest.TestCase):
    def test_surface_array_groups_faces_and_flux_by_gray_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spectrum = root / "spectrum.spectrum"
            csv_file = root / "gray.csv"
            spectrum.touch()
            _write_flux_csv(csv_file, ((1023, 512), (512, 0)))
            array = ArrayConfig(2, 2, 2.0, 4.0)
            flux_map = FluxMapConfig.load(csv_file, array)
            lightbox = _FakeSurfaceLightbox()
            config = SurfaceConfig(1.0, 1.0, LambertianConfig(3.0, 180.0, spectrum))

            _, sources, active_faces = SpeosGateway()._build_surface_array(
                lightbox,
                iter_array_elements(2, 2, 2.0, 4.0),
                config,
                flux_map,
                lambda update: None,
                lambda: False,
            )

            self.assertEqual([source.name for source in sources], ["Gray512", "Gray1023"])
            gray_512, gray_1023 = sources
            self.assertEqual(len(gray_512.exitance.geometries), 2)
            self.assertEqual(len(gray_1023.exitance.geometries), 1)
            self.assertEqual(len(active_faces), 3)
            self.assertAlmostEqual(gray_512.flux.value, 3.0 * 512 / 1023 * 2)
            self.assertEqual(gray_1023.flux.value, 3.0)

    def test_generation_temporarily_disables_graphics_cache(self) -> None:
        original_graphics_value = speos_gateway.speos_general_methods._GRAPHICS_AVAILABLE
        speos = SimpleNamespace(close=Mock())
        lightbox = _FakeLightbox()
        parent_project = SimpleNamespace(create_lightbox=Mock(return_value=lightbox))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ray_file = root / "source.ray"
            flux_csv = root / "flux.csv"
            rpc_directory = root / "SPEOS_RPC"
            ray_file.touch()
            _write_flux_csv(flux_csv, ((1023,),))
            rpc_directory.mkdir()
            config = GenerationConfig(
                array=ArrayConfig(1, 1, 1.0, 1.0),
                source=RayFileConfig(ray_file, False, 1.0),
                flux_map=FluxMapConfig.load(flux_csv, ArrayConfig(1, 1, 1.0, 1.0)),
                export=ExportConfig(root, "graphics"),
                speos=SpeosConfig(rpc_directory),
            )
            observed_graphics_values: list[bool | None] = []
            def observe_create_source() -> None:
                observed_graphics_values.append(speos_gateway.speos_general_methods._GRAPHICS_AVAILABLE)

            lightbox.on_create_source = observe_create_source
            gateway = SpeosGateway(Mock(return_value=speos), Mock(return_value=parent_project))
            gateway.generate(config)

        self.assertEqual(observed_graphics_values, [False])
        self.assertEqual(speos_gateway.speos_general_methods._GRAPHICS_AVAILABLE, original_graphics_value)

    def test_rayfile_array_is_named_positioned_committed_and_exported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ray_file = root / "source.ray"
            flux_csv = root / "flux.csv"
            rpc_directory = root / "SPEOS_RPC"
            ray_file.touch()
            _write_flux_csv(flux_csv, ((1023, 0), (512, 1023)))
            rpc_directory.mkdir()
            speos = SimpleNamespace(close=Mock())
            lightbox = _FakeLightbox()
            parent_project = SimpleNamespace(create_lightbox=Mock(return_value=lightbox))
            launcher = Mock(return_value=speos)
            project_factory = Mock(return_value=parent_project)
            config = GenerationConfig(
                array=ArrayConfig(2, 2, 2.0, 4.0),
                source=RayFileConfig(ray_file, False, 2.0),
                flux_map=FluxMapConfig.load(flux_csv, ArrayConfig(2, 2, 2.0, 4.0)),
                export=ExportConfig(root, "array"),
                speos=SpeosConfig(rpc_directory),
            )

            output = SpeosGateway(launcher, project_factory).generate(config)

            self.assertEqual(output, root / "array.SPEOSLightBox")
            self.assertTrue(output.is_dir())
            self.assertEqual([source.name for source in lightbox.sources], ["X0Y0", "X1Y0", "X1Y1"])
            self.assertEqual(
                [source.axis_system[:3] for source in lightbox.sources],
                [[-1.0, 2.0, 0.0], [-1.0, -2.0, 0.0], [1.0, -2.0, 0.0]],
            )
            self.assertEqual(
                [source.flux.value for source in lightbox.sources],
                [2.0, 2.0 * 512 / 1023, 2.0],
            )
            lightbox.commit.assert_called_once_with()
            lightbox.export.assert_called_once_with(root / "array.SPEOSLightBox")
            speos.close.assert_called_once_with()

    def test_surface_source_commit_persists_each_intensity_before_lightbox_commit(self) -> None:
        sources = [_FakeSurfaceSource(), _FakeSurfaceSource()]
        lightbox = SimpleNamespace(project=SimpleNamespace(commit=Mock()))
        progress: list[GenerationProgress] = []

        SpeosGateway()._commit_surface_sources(lightbox, sources, progress.append, lambda: False)

        for source in sources:
            source.intensity.commit.assert_called_once_with()
            self.assertEqual(source._source_template.surface.intensity_guid, "intensity-guid")
        lightbox.project.commit.assert_called_once_with()
        self.assertEqual(progress[-1].stage, "commit sources")
        self.assertEqual(progress[-1].completed, 1)

    def test_surface_geometry_is_committed_before_its_sources(self) -> None:
        root_part = SimpleNamespace(commit=Mock())
        progress: list[GenerationProgress] = []

        SpeosGateway()._commit_surface_geometry(root_part, progress.append)

        root_part.commit.assert_called_once_with()
        self.assertEqual(progress[-1].stage, "commit geometry")
        self.assertEqual(progress[-1].completed, 1)

    def test_absorber_property_uses_mirror_zero_on_active_faces(self) -> None:
        absorber = SimpleNamespace(geometries=None, commit=Mock())
        lightbox = SimpleNamespace(create_optical_property=Mock(return_value=absorber))
        faces: list[object] = [SimpleNamespace(), SimpleNamespace()]
        progress: list[GenerationProgress] = []

        SpeosGateway()._commit_absorber_property(lightbox, faces, progress.append)

        parameters = lightbox.create_optical_property.call_args.kwargs["parameters"]
        self.assertEqual(parameters.sop_parameters.reflectance, 0)
        self.assertEqual(absorber.geometries, faces)
        absorber.commit.assert_called_once_with()
        self.assertEqual(progress[-1].stage, "commit absorber")


class _FakeRaySource:
    def __init__(self, name: str) -> None:
        self.name = name
        self.ray_file_uri = None
        self.axis_system: list[float] = []
        self.flux = SimpleNamespace(set_luminous=Mock(), value=None)
        self.set_flux_from_ray_file = Mock()


class _FakeSurfaceSource:
    def __init__(self) -> None:
        self.intensity = SimpleNamespace(
            commit=Mock(),
            intensity_template_link=SimpleNamespace(key="intensity-guid"),
        )
        self._source_template = SimpleNamespace(surface=SimpleNamespace(intensity_guid=""))


class _FakeFace:
    def __init__(self, name: str) -> None:
        self.name = name
        self.vertices: list[float] = []
        self.normals: list[float] = []
        self.facets: list[int] = []


class _FakeBody:
    def create_face(self, name: str) -> _FakeFace:
        return _FakeFace(name)


class _FakeRootPart:
    def create_body(self, name: str) -> _FakeBody:
        return _FakeBody()


class _FakeSurfaceGeneratedSource:
    def __init__(self, name: str) -> None:
        self.name = name
        self.flux = SimpleNamespace(set_luminous=Mock(), value=None)
        self.spectrum = SimpleNamespace(set_library=Mock(return_value=SimpleNamespace(file_uri=None)))
        self.cosine = SimpleNamespace(n=None, total_angle=None)
        self.intensity = SimpleNamespace(set_cos=Mock(return_value=self.cosine))
        self.exitance = SimpleNamespace(geometries=[])

    def set_exitance_constant(self):
        return self.exitance


class _FakeSurfaceLightbox:
    def __init__(self) -> None:
        self.sources: list[_FakeSurfaceGeneratedSource] = []

    def create_root_part(self) -> _FakeRootPart:
        return _FakeRootPart()

    def create_source(self, name: str, feature_type) -> _FakeSurfaceGeneratedSource:
        source = _FakeSurfaceGeneratedSource(name)
        self.sources.append(source)
        return source


class _FakeLightbox:
    def __init__(self) -> None:
        self.sources: list[_FakeRaySource] = []
        self.on_create_source: Callable[[], None] | None = None
        self.commit = Mock()
        self.export = Mock(side_effect=self._export)

    def create_source(self, name: str, feature_type) -> _FakeRaySource:
        if self.on_create_source is not None:
            self.on_create_source()
        source = _FakeRaySource(name)
        self.sources.append(source)
        return source

    @staticmethod
    def _export(path: Path) -> None:
        path.mkdir()


def _write_flux_csv(path: Path, rows: tuple[tuple[float, ...], ...]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        csv.writer(file).writerows(rows)


if __name__ == "__main__":
    unittest.main()