#!/usr/bin/env python3
"""
Evaluates the workbook's formulas and checks the results.

verify_math.py proves the arithmetic is right. This proves Excel will actually
compute it -- that every formula parses, resolves its references, and produces
the expected value rather than #REF!/#VALUE!/#N/A.

It builds a scaled-down variant of the workbook first. The formulas are
character-for-character the same; only MAX_ROWS (the bound on the lookup grids)
and the number of pre-filled Schedule rows differ, because the formula engine
materialises those grids in memory and the shipped 100,000-row bound exhausts it.

Needs a formula engine that the shipped workbook does not:

    pip install formulas

    python3 verify_formulas.py
"""

import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_template as bt

try:
    import formulas
except ImportError:
    print("This check needs the 'formulas' package:  pip install formulas")
    raise SystemExit(2)

# row -> (splitter, tier, nearest address, distance ft, QA flags)
EXPECTED = {
    # row: (splitter, tier, ratio, nearest address, distance ft, QA flags)
    6: ("SPL-001", "Primary", "1x8", "100 N HIGH ST", 22.9, ""),
    7: ("SPL-002", "Secondary", "1x16", "212 W 5TH AVE", 22.9, ""),
    8: ("SPL-003", "Tertiary", "1x128", "415 E LANE AVE", 22.9, ""),
    9: ("SPL-004", "", "", "", 22270.6, "no-tier no-ratio address-too-far"),
}


def build_small(path: Path) -> None:
    bt.MAX_ROWS = 60
    bt.SPL = f"Splitters!$A$1:$CZ${bt.MAX_ROWS}"
    bt.ADDR = f"Addresses!$A$1:$CZ${bt.MAX_ROWS}"
    bt.SCHEDULE_ROWS = 6
    bt.OUT = path
    bt.main()


def main() -> int:
    tmp = Path(tempfile.mkdtemp()) / "small.xlsx"
    build_small(tmp)

    model = formulas.ExcelModel().loads(str(tmp)).finish()
    sol = model.calculate()

    def val(cell: str):
        # Anchor on the Schedule sheet: Instructions and Setup also have a B6,
        # and matching the cell reference alone quietly returns the wrong one.
        for key in sol:
            if "]SCHEDULE'!" in key.upper() and key.upper().endswith(f"!{cell}"):
                try:
                    return sol[key].value[0, 0]
                except Exception:
                    return sol[key]
        return "<missing>"

    def norm(v) -> str:
        return "" if v is None else str(v).strip()

    problems: list[str] = []
    header = f"{'row':>3}  {'splitter':<9} {'tier':<10} {'ratio':<7} {'address':<15} {'ft':>9}  flags"
    print(header)
    print("-" * len(header))

    for row, (splitter, tier, ratio, address, distance, flags) in EXPECTED.items():
        got = {c: val(f"{c}{row}") for c in "BDEHIJK"}

        for col, value in got.items():
            if isinstance(value, str) and value.startswith("#"):
                problems.append(f"Schedule!{col}{row} evaluated to {value}")

        if norm(got["B"]) != splitter:
            problems.append(f"B{row} splitter: {got['B']!r} != {splitter!r}")
        if norm(got["D"]) != tier:
            problems.append(f"D{row} tier: {got['D']!r} != {tier!r}")
        if norm(got["E"]) != ratio:
            problems.append(f"E{row} ratio: {got['E']!r} != {ratio!r}")
        if norm(got["H"]) != address:
            problems.append(f"H{row} address: {got['H']!r} != {address!r}")
        if norm(got["J"]) != flags:
            problems.append(f"J{row} flags: {got['J']!r} != {flags!r}")
        try:
            if abs(float(got["I"]) - distance) > 0.1:
                problems.append(f"I{row} distance: {got['I']!r} != {distance}")
        except (TypeError, ValueError):
            problems.append(f"I{row} distance is not a number: {got['I']!r}")

        dist = got["I"]
        dist_s = f"{dist:9.1f}" if isinstance(dist, (int, float)) else f"{str(dist):>9}"
        print(
            f"{row:>3}  {norm(got['B']):<9} {norm(got['D']):<10} {norm(got['E']):<7} "
            f"{norm(got['H']):<15} {dist_s}  {norm(got['J'])}"
        )

    print()
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  -", p)
        return 1
    print("every formula evaluates, and every value matches the expectation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
