import unittest

from microled_lightbox.layout import (
    iter_array_elements,
    rayfile_axis_system,
    rectangle_mesh,
)


class ArrayLayoutTests(unittest.TestCase):
    def test_even_array_is_centered_and_ordered_from_top_left(self) -> None:
        elements = list(iter_array_elements(4, 2, 2.0, 4.0))

        self.assertEqual(elements[0].name, "X0Y0")
        self.assertEqual(elements[0].center, (-3.0, 2.0, 0.0))
        self.assertEqual(elements[-1].name, "X1Y3")
        self.assertEqual(elements[-1].center, (3.0, -2.0, 0.0))
        self.assertAlmostEqual(sum(item.center[0] for item in elements), 0.0)
        self.assertAlmostEqual(sum(item.center[1] for item in elements), 0.0)

    def test_odd_array_contains_the_global_origin(self) -> None:
        elements = list(iter_array_elements(3, 3, 1.0, 1.0))

        self.assertEqual(elements[4].name, "X1Y1")
        self.assertEqual(elements[4].center, (0.0, 0.0, 0.0))

    def test_requested_name_uses_row_then_column(self) -> None:
        elements = list(iter_array_elements(7, 6, 1.0, 1.0))

        self.assertEqual(elements[5 * 7 + 6].name, "X5Y6")

    def test_maximum_array_has_expected_endpoints(self) -> None:
        elements = list(iter_array_elements(300, 150, 0.1, 0.2))

        self.assertEqual(len(elements), 45_000)
        for actual, expected in zip(elements[0].center, (-14.95, 14.9, 0.0)):
            self.assertAlmostEqual(actual, expected)
        for actual, expected in zip(elements[-1].center, (14.95, -14.9, 0.0)):
            self.assertAlmostEqual(actual, expected)

    def test_invalid_layout_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            list(iter_array_elements(0, 1, 1.0, 1.0))
        with self.assertRaises(ValueError):
            list(iter_array_elements(1, 1, 0.0, 1.0))


class GeometryTests(unittest.TestCase):
    def test_rectangle_mesh_has_positive_z_winding(self) -> None:
        mesh = rectangle_mesh((1.0, 2.0, 0.0), 2.0, 4.0)

        self.assertEqual(mesh.facets, (0, 1, 2, 0, 2, 3))
        self.assertEqual(mesh.vertices[:3], (0.0, 0.0, 0.0))
        self.assertEqual(mesh.vertices[6:9], (2.0, 4.0, 0.0))
        self.assertEqual(mesh.normals, (0.0, 0.0, 1.0) * 4)
        self.assertEqual(len(mesh.normals), len(mesh.vertices))

    def test_rayfile_axes_are_normalized_and_point_to_positive_z(self) -> None:
        axis_system = rayfile_axis_system((2.0, 3.0, 0.0), (2, 0, 0), (0, 4, 0))

        self.assertEqual(axis_system, (2.0, 3.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0))

    def test_nonorthogonal_rayfile_axes_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            rayfile_axis_system((0.0, 0.0, 0.0), (1, 0, 0), (1, 1, 0))


if __name__ == "__main__":
    unittest.main()