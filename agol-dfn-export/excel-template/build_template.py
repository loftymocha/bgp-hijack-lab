#!/usr/bin/env python3
"""
Builds DFN-Splitter-Matcher.xlsx -- a zero-install Excel workbook that turns two
AGOL CSV exports into a finished splitter schedule.

The user pastes their splitter export and their address-point export into two
sheets, tells the Setup sheet which columns hold what, and the Schedule sheet
computes the nearest address, the distance to it, and a normalized tier label
for every splitter.

Everything is formulas -- nothing here is precomputed -- so the sheet updates
when they paste new data. Only pre-2007 functions are used (INDEX, MATCH,
SUMPRODUCT, COUNTBLANK) and nothing volatile, so it works on older Excel installs with no
dynamic-array support.

    python3 build_template.py
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

FONT = "Arial"
OUT = Path(__file__).resolve().parent / "DFN-Splitter-Matcher.xlsx"

# How many splitter rows the Schedule sheet is pre-filled for.
SCHEDULE_ROWS = 500
HDR = 5           # Schedule header row
FIRST = HDR + 1   # Schedule first data row

INPUT_FONT = Font(name=FONT, color="0000FF", bold=True)
INPUT_FILL = PatternFill("solid", fgColor="FFFF00")
LABEL_FONT = Font(name=FONT, bold=True)
BODY_FONT = Font(name=FONT)
NOTE_FONT = Font(name=FONT, italic=True, color="595959", size=9)
H1_FONT = Font(name=FONT, bold=True, size=14)
HEADER_FILL = PatternFill("solid", fgColor="1F3864")
HEADER_FONT = Font(name=FONT, color="FFFFFF", bold=True)
SAMPLE_FILL = PatternFill("solid", fgColor="EDEDED")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def put(ws, cell, value, font=BODY_FONT, fill=None, number_format=None, comment=None):
    c = ws[cell]
    c.value = value
    c.font = font
    if fill:
        c.fill = fill
    if number_format:
        c.number_format = number_format
    if comment:
        c.comment = Comment(comment, "DFN template")
    return c


def widths(ws, mapping):
    for letter, width in mapping.items():
        ws.column_dimensions[letter].width = width


# --------------------------------------------------------------------------
# Instructions
# --------------------------------------------------------------------------


def build_instructions(wb):
    ws = wb.create_sheet("Instructions")
    widths(ws, {"A": 4, "B": 104})

    put(ws, "B2", "DFN Splitter Schedule - how to use this workbook", H1_FONT)

    steps = [
        ("", ""),
        ("What this does", ""),
        (
            "",
            "You paste two exports out of ArcGIS Online. It gives you back one sheet with every "
            "splitter, its tier, and the nearest address already matched -- no manual lookups.",
        ),
        ("", ""),
        ("Step 1 - export your splitter layer", ""),
        (
            "",
            "In your AGOL site, open the splitter layer's item page. Click Export Data > "
            "Export to CSV. Open the file and copy everything, headers included.",
        ),
        ("", "Paste it into the 'Splitters' tab, starting at cell A1."),
        ("", ""),
        ("Step 2 - export your address point layer", ""),
        (
            "",
            "Same thing for the address layer. Paste into the 'Addresses' tab at A1. "
            "If your map has no address layer, see 'If you have no address layer' below.",
        ),
        ("", ""),
        ("Step 3 - fill in the Setup tab", ""),
        (
            "",
            "Every yellow cell on the Setup tab needs a value. You are telling the workbook which "
            "column letter holds which piece of information, and how many rows you pasted.",
        ),
        (
            "",
            "The AGOL export names the coordinate columns 'x' and 'y' -- x is longitude, "
            "y is latitude. Check which letters they landed in and enter those.",
        ),
        ("", ""),
        ("Step 4 - fill in the tier lookup on the Setup tab", ""),
        (
            "",
            "Sort the tier column on your Splitters tab to see the distinct values it actually "
            "holds. Type each one in the left column of the lookup and the tier it means on the "
            "right. Spelling must match your data exactly.",
        ),
        ("", ""),
        ("Step 5 - read the Schedule tab", ""),
        (
            "",
            "It fills in automatically. Sort or filter the QA Flags column: every row with a flag "
            "is one you still need to look at. Rows with no flag are done.",
        ),
        ("", ""),
        ("Flags and what they mean", ""),
        ("", "no-tier            the tier value on that splitter is not in your lookup table"),
        ("", "no-ratio           the split ratio field is empty for that splitter"),
        ("", "no-geometry        the splitter has no coordinates in the export"),
        (
            "",
            "address-too-far    the closest address is farther than your distance limit, so it "
            "was left blank rather than guessed at",
        ),
        ("", ""),
        ("If you have no address layer", ""),
        (
            "",
            "This workbook can only match against addresses you give it. With no address layer "
            "there is nothing to match, and you would need reverse geocoding instead -- which "
            "means the Python script in the parent folder, or an ArcGIS Notebook.",
        ),
        ("", ""),
        ("If it feels slow", ""),
        (
            "",
            "Every splitter is compared against every address, so the work grows with both. Set "
            "the last-row numbers on Setup to your real row counts rather than leaving them high, "
            "and it will settle down. If it is still slow, press Ctrl+Alt+F9 once and let it finish.",
        ),
        ("", ""),
        ("Accuracy note", ""),
        (
            "",
            "Distances use a flat-earth approximation at 364,000 ft per degree of latitude. "
            "It runs about 0.2% off a round-earth calculation -- around a foot at 500 ft -- and "
            "because that is a uniform scaling it cannot change which address comes out nearest. "
            "It is not suitable for distances of many miles.",
        ),
        ("", ""),
        ("The sample data", ""),
        (
            "",
            "The Splitters and Addresses tabs ship with four splitters and three addresses of fake "
            "data, shaded grey, so you can see the expected format and watch the Schedule work. "
            "Delete those rows before you paste your own.",
        ),
    ]

    row = 3
    for label, text in steps:
        if label:
            put(ws, f"B{row}", label, LABEL_FONT)
        elif text:
            c = put(ws, f"B{row}", text)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            ws.row_dimensions[row].height = 30 if len(text) > 100 else 15
        row += 1
    return ws


# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------

SETUP_ROWS = {
    "splitter_first": 5,
    "splitter_last": 6,
    "splitter_id": 7,
    "splitter_tier": 8,
    "splitter_ratio": 9,
    "splitter_x": 10,
    "splitter_y": 11,
    "address_first": 15,
    "address_last": 16,
    "address_num": 17,
    "address_street": 18,
    "address_x": 19,
    "address_y": 20,
    "max_ft": 24,
    "ft_per_deg": 25,
    "tier_map_first": 30,
    "tier_map_last": 44,
}


def s(key: str) -> str:
    """Absolute reference to a Setup input cell (the value the user types)."""
    return f"Setup!$B${SETUP_ROWS[key]}"


def ci(key: str) -> str:
    """Absolute reference to the resolved column NUMBER for a Setup field."""
    return f"Setup!$C${SETUP_ROWS[key]}"


# The lookup grids are bounded on both axes rather than written as whole-column
# references. Row 1 is included so a sheet row number indexes the grid directly.
# Widen MAX_ROWS if a layer ever exceeds it; column CZ is 104 columns, which is
# far more than an AGOL export carries.
MAX_ROWS = 100000
SPL = f"Splitters!$A$1:$CZ${MAX_ROWS}"
ADDR = f"Addresses!$A$1:$CZ${MAX_ROWS}"


def build_setup(wb):
    ws = wb.create_sheet("Setup")
    widths(ws, {"A": 30, "B": 20, "C": 11, "D": 60})

    put(ws, "A2", "Setup", H1_FONT)
    put(
        ws,
        "A3",
        "Fill in every yellow cell. Blue bold = you type it. Column C fills itself in -- "
        "if it says 'NOT FOUND', the name you typed does not match a header on that tab.",
        NOTE_FONT,
    )

    def rowfield(row, label, value, note, fmt=None):
        """A plain number the user types (row counts, distance limit)."""
        put(ws, f"A{row}", label, LABEL_FONT)
        put(ws, f"B{row}", value, INPUT_FONT, INPUT_FILL, fmt)
        put(ws, f"D{row}", note, NOTE_FONT)

    def colfield(row, label, value, sheet, note, optional=False):
        """A column HEADER NAME the user types; C resolves it to a column number."""
        put(ws, f"A{row}", label, LABEL_FONT)
        put(ws, f"B{row}", value, INPUT_FONT, INPUT_FILL)
        fallback = "1" if optional else '"NOT FOUND"'
        blank_guard = f'IF($B{row}="",1,' if optional else "("
        put(
            ws,
            f"C{row}",
            f'={blank_guard}IFERROR(MATCH($B{row},{sheet}!$1:$1,0),{fallback}))',
            BODY_FONT,
        )
        put(ws, f"D{row}", note, NOTE_FONT)

    put(ws, "C4", "Column #", LABEL_FONT)
    put(ws, "A4", "SPLITTERS TAB", LABEL_FONT)
    rowfield(5, "First data row", 2, "Row your first splitter is on (2 if headers are in row 1)")
    rowfield(6, "Last data row", 5, "Row your last splitter is on -- set to your real count")
    colfield(7, "Splitter ID column", "SPLITTER_ID", "Splitters",
             "Type the column HEADING exactly as it appears in row 1 of that tab")
    colfield(8, "Tier / level column", "SPLTR_LEVEL", "Splitters",
             "The heading of the column holding primary/secondary/tertiary")
    colfield(9, "Split ratio column", "SPLIT_RATIO", "Splitters",
             "The heading of the column holding 1x8, 1x16, 1x32 etc.")
    colfield(10, "Longitude column", "x", "Splitters", "The AGOL export calls this 'x'")
    colfield(11, "Latitude column", "y", "Splitters", "The AGOL export calls this 'y'")

    put(ws, "A14", "ADDRESSES TAB", LABEL_FONT)
    rowfield(15, "First data row", 2, "Row your first address is on")
    rowfield(16, "Last data row", 4, "Row your last address is on -- set to your real count")
    colfield(17, "House number column", "HOUSE_NUM", "Addresses",
             "The heading of the column holding the street number")
    colfield(18, "Street name column", "STREET", "Addresses",
             "Leave the yellow cell BLANK if one column already holds the whole address",
             optional=True)
    colfield(19, "Longitude column", "x", "Addresses", "The AGOL export calls this 'x'")
    colfield(20, "Latitude column", "y", "Addresses", "The AGOL export calls this 'y'")

    put(ws, "A23", "MATCHING RULES", LABEL_FONT)
    rowfield(
        24,
        "Max address distance (feet)",
        500,
        "Anything farther is flagged rather than filled in, so a splitter in open ground "
        "is not labelled with a house a quarter mile away",
        "#,##0",
    )
    put(ws, "A25", "Feet per degree latitude", LABEL_FONT)
    put(ws, "B25", 364000, BODY_FONT, None, "#,##0").comment = Comment(
        "Standard conversion: one degree of latitude is about 364,000 ft (69 miles).\n"
        "Longitude is scaled by the cosine of latitude in the distance formula.\n"
        "You should not need to change this.",
        "DFN template",
    )
    put(ws, "D25", "Constant -- you should not need to change this.", NOTE_FONT)

    put(ws, "A28", "TIER LOOKUP", LABEL_FONT)
    put(ws, "A29", "Left: the exact value in your tier column. Right: what it means.", NOTE_FONT)
    put(ws, "B29", "Value in your data", LABEL_FONT)
    put(ws, "C29", "Tier", LABEL_FONT)

    seed = [("Level 1", "Primary"), ("Level 2", "Secondary"), ("Level 3", "Tertiary")]
    for i in range(SETUP_ROWS["tier_map_first"], SETUP_ROWS["tier_map_last"] + 1):
        idx = i - SETUP_ROWS["tier_map_first"]
        value, tier = seed[idx] if idx < len(seed) else ("", "")
        put(ws, f"B{i}", value, INPUT_FONT, INPUT_FILL)
        put(ws, f"C{i}", tier, INPUT_FONT, INPUT_FILL)
    put(
        ws,
        f"D{SETUP_ROWS['tier_map_first']}",
        "Example values shown -- replace with the ones your layer actually uses.",
        NOTE_FONT,
    )
    return ws


# --------------------------------------------------------------------------
# Data tabs (sample rows the user deletes)
# --------------------------------------------------------------------------


def build_data_tab(wb, title, headers, rows, note):
    ws = wb.create_sheet(title)
    for col, header in enumerate(headers, start=1):
        c = ws.cell(row=1, column=col, value=header)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
    for r, values in enumerate(rows, start=2):
        for col, value in enumerate(values, start=1):
            c = ws.cell(row=r, column=col, value=value)
            c.font = BODY_FONT
            c.fill = SAMPLE_FILL
            if isinstance(value, float):
                c.number_format = "0.000000"
    ws.cell(row=len(rows) + 3, column=1, value=note).font = NOTE_FONT
    ws.freeze_panes = "A2"
    widths(ws, {get_column_letter(i): 16 for i in range(1, len(headers) + 1)})
    widths(ws, {"B": 20, "C": 20})
    return ws


SPLITTER_HEADERS = ["OBJECTID", "SPLITTER_ID", "SPLTR_LEVEL", "SPLIT_RATIO", "x", "y"]
SPLITTER_SAMPLE = [
    [1, "SPL-001", "Level 1", "1x8", -83.000000, 40.000000],
    [2, "SPL-002", "Level 2", "1x16", -83.001000, 40.000500],
    [3, "SPL-003", "Level 3", "1x32", -83.002000, 40.001000],
    [4, "SPL-004", None, "1x32", -83.050000, 40.050000],
]

ADDRESS_HEADERS = ["OBJECTID", "HOUSE_NUM", "STREET", "x", "y"]
ADDRESS_SAMPLE = [
    [1, "100", "N HIGH ST", -83.000050, 40.000050],
    [2, "212", "W 5TH AVE", -83.001050, 40.000550],
    [3, "415", "E LANE AVE", -83.002050, 40.001050],
]


# --------------------------------------------------------------------------
# Schedule
# --------------------------------------------------------------------------

SCHEDULE_HEADERS = [
    "Src Row",
    "Splitter",
    "Raw Tier Value",
    "Tier",
    "Ratio",
    "Longitude",
    "Latitude",
    "Nearest Address",
    "Distance (ft)",
    "QA Flags",
    "min dist^2",
    "addr row",
]


def cell_from(grid: str, col_key: str, row_ref: str) -> str:
    """One cell, located by resolved column number. INDEX is not volatile."""
    return f"INDEX({grid},{row_ref},{ci(col_key)})"


def range_from(grid: str, col_key: str) -> str:
    """
    A bounded column range built as INDEX():INDEX().

    This is the non-volatile equivalent of INDIRECT("Addresses!D2:D5000") -- it
    resizes with the row counts on Setup but does not force a full recalculation
    of the workbook every time any cell changes.
    """
    return (
        f"INDEX({grid},{s('address_first')},{ci(col_key)})"
        f":INDEX({grid},{s('address_last')},{ci(col_key)})"
    )


def build_schedule(wb):
    ws = wb.create_sheet("Schedule", 0)
    put(ws, "A1", "DFN Splitter Schedule", H1_FONT)
    put(
        ws,
        "A2",
        "Computed from the Splitters and Addresses tabs. Filter the QA Flags column "
        "for the rows that still need you.",
        NOTE_FONT,
    )

    last = FIRST + SCHEDULE_ROWS - 1
    put(ws, "H2", "Splitters:", LABEL_FONT)
    put(ws, "I2", f'=COUNTIF($B${FIRST}:$B${last},"?*")', BODY_FONT, None, "#,##0")
    put(ws, "H3", "Needing review:", LABEL_FONT)
    put(ws, "I3", f'=COUNTIF($J${FIRST}:$J${last},"?*")', BODY_FONT, None, "#,##0")

    for col, header in enumerate(SCHEDULE_HEADERS, start=1):
        c = ws.cell(row=HDR, column=col, value=header)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.alignment = Alignment(wrap_text=True, vertical="center")

    # Working columns K and L feed H and I; keeping them as real columns avoids
    # recomputing the whole distance array twice and keeps MATCH exact.
    ws.cell(row=HDR, column=11).comment = Comment(
        "Working column: squared distance in square feet to the closest address.\n"
        "Squared so the MATCH below finds the identical value with no rounding drift.",
        "DFN template",
    )

    ax = range_from(ADDR, "address_x")
    ay = range_from(ADDR, "address_y")

    for r in range(FIRST, last + 1):
        src = f"$A{r}"
        # distance array in ft^2, longitude scaled by cos(latitude)
        dist2 = (
            f"(({ax}-$F{r})*COS(RADIANS($G{r}))*{s('ft_per_deg')})^2"
            f"+(({ay}-$G{r})*{s('ft_per_deg')})^2"
        )

        ws[f"A{r}"] = (
            f"=IF({s('splitter_first')}+ROW()-{FIRST}>{s('splitter_last')},\"\","
            f"{s('splitter_first')}+ROW()-{FIRST})"
        )

        def blank_safe(col_key):
            ref = cell_from(SPL, col_key, src)
            return f'=IF({src}="","",IF(COUNTBLANK({ref})=1,"",{ref}))'

        ws[f"B{r}"] = blank_safe("splitter_id")
        ws[f"C{r}"] = blank_safe("splitter_tier")
        ws[f"D{r}"] = (
            f'=IF({src}="","",IFERROR(INDEX(Setup!$C${SETUP_ROWS["tier_map_first"]}:'
            f'$C${SETUP_ROWS["tier_map_last"]},MATCH($C{r},'
            f'Setup!$B${SETUP_ROWS["tier_map_first"]}:$B${SETUP_ROWS["tier_map_last"]},0)),""))'
        )
        ws[f"E{r}"] = blank_safe("splitter_ratio")
        ws[f"F{r}"] = blank_safe("splitter_x")
        ws[f"G{r}"] = blank_safe("splitter_y")

        ws[f"K{r}"] = (
            f'=IF(OR({src}="",$F{r}="",$G{r}=""),"",SUMPRODUCT(MIN({dist2})))'
        )
        ws[f"L{r}"] = (
            f'=IF($K{r}="","",{s("address_first")}+SUMPRODUCT(MATCH($K{r},{dist2},0))-1)'
        )
        ws[f"I{r}"] = f'=IF($K{r}="","",SQRT($K{r}))'

        num = cell_from(ADDR, "address_num", f"$L{r}")
        street = cell_from(ADDR, "address_street", f"$L{r}")
        ws[f"H{r}"] = (
            f'=IF($L{r}="","",IF($I{r}>{s("max_ft")},"",'
            f'TRIM({num}&" "&IF({s("address_street")}="","",{street}))))'
        )
        ws[f"J{r}"] = (
            f'=IF({src}="","",TRIM('
            f'IF($D{r}="","no-tier ","")'
            f'&IF($E{r}="","no-ratio ","")'
            f'&IF($I{r}="","no-geometry ",IF($I{r}>{s("max_ft")},"address-too-far ",""))'
            f"))"
        )

        for col in range(1, len(SCHEDULE_HEADERS) + 1):
            c = ws.cell(row=r, column=col)
            c.font = BODY_FONT
            c.border = BORDER
        ws[f"F{r}"].number_format = "0.000000"
        ws[f"G{r}"].number_format = "0.000000"
        ws[f"I{r}"].number_format = "#,##0.0"
        ws[f"K{r}"].number_format = "#,##0"

    ws.freeze_panes = f"A{FIRST}"
    ws.auto_filter.ref = f"A{HDR}:J{last}"
    widths(
        ws,
        {
            "A": 9, "B": 18, "C": 16, "D": 12, "E": 10, "F": 13,
            "G": 13, "H": 34, "I": 13, "J": 30, "K": 14, "L": 10,
        },
    )
    ws.column_dimensions["K"].hidden = True
    ws.column_dimensions["L"].hidden = True
    return ws


def main() -> None:
    wb = Workbook()
    wb.remove(wb.active)
    build_schedule(wb)
    build_instructions(wb)
    build_setup(wb)
    build_data_tab(
        wb, "Splitters", SPLITTER_HEADERS, SPLITTER_SAMPLE,
        "Sample data (grey) -- delete these rows and paste your AGOL export at A1.",
    )
    build_data_tab(
        wb, "Addresses", ADDRESS_HEADERS, ADDRESS_SAMPLE,
        "Sample data (grey) -- delete these rows and paste your AGOL export at A1.",
    )
    wb.move_sheet("Instructions", offset=-1)
    wb.save(OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
