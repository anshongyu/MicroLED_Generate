import csv
import tempfile
import unittest
from pathlib import Path

from microled_lightbox.arrow_csv import (
    ACTIVE_VALUE,
    COLUMNS,
    ROWS,
    build_right_turn_arrow,
    write_right_turn_arrow_csv,
)


class RightTurnArrowTests(unittest.TestCase):
    def test_arrow_has_requested_dimensions_and_expected_values(self) -> None:
        matrix = build_right_turn_arrow()

        self.assertEqual(len(matrix), ROWS)
        self.assertTrue(all(len(row) == COLUMNS for row in matrix))
        self.assertTrue(all(value in (0, ACTIVE_VALUE) for row in matrix for value in row))

    def test_arrow_points_from_bottom_up_then_right(self) -> None:
        matrix = build_right_turn_arrow()

        self.assertEqual(matrix[70][68], ACTIVE_VALUE)
        self.assertEqual(matrix[48][68], ACTIVE_VALUE)
        self.assertEqual(matrix[20][100], ACTIVE_VALUE)
        self.assertEqual(matrix[16][180], ACTIVE_VALUE)
        self.assertEqual(matrix[16][236], ACTIVE_VALUE)
        self.assertEqual(matrix[0][0], 0)
        self.assertEqual(matrix[81][245], 0)

    def test_writer_creates_a_headerless_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "arrow.csv"
            result = write_right_turn_arrow_csv(output_path)

            with output_path.open(newline="", encoding="utf-8") as file:
                rows = list(csv.reader(file))

        self.assertEqual(result, output_path)
        self.assertEqual(len(rows), ROWS)
        self.assertTrue(all(len(row) == COLUMNS for row in rows))
        self.assertEqual({value for row in rows for value in row}, {"0", str(ACTIVE_VALUE)})


if __name__ == "__main__":
    unittest.main()