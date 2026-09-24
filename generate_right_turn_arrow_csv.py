"""Generate the repository's fixed-size right-turn arrow CSV file."""

from pathlib import Path

from microled_lightbox.arrow_csv import write_right_turn_arrow_csv


def main() -> int:
    output_path = Path(__file__).resolve().parent / "right_turn_arrow.csv"
    write_right_turn_arrow_csv(output_path)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())