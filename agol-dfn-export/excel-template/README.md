# DFN-Splitter-Matcher.xlsx — the no-install option

An Excel workbook that does the splitter/address matching with formulas alone.
Nothing to install, nothing to run, no Python. If your work laptop is locked
down or you'd rather not run scripts on it, this is the path.

It does less than the Python script in the parent folder — it works on two layers
rather than the whole map, and it can't reverse geocode — but it removes the same
manual step, and it does it inside a program you already have open.

## How it works

1. Get your **splitter layer** into the `Splitters` tab. Either open the layer's
   item page → **Export Data → Export to CSV**, or — if that button isn't there —
   use [`../powerquery/agol-layer.pq`](../powerquery/), which reads the layer
   without needing export permission.
2. Get your **address point layer** into the `Addresses` tab the same way.
3. On the `Setup` tab, type the column headings for splitter ID, tier, ratio, and
   the `x`/`y` coordinate columns, plus how many rows you pasted.
4. Fill in the tier lookup — the exact values your data uses (`Level 1`, `P`,
   `PRIMARY`…) mapped to Primary / Secondary / Tertiary.
5. Read the `Schedule` tab. Filter the **QA Flags** column: flagged rows need you,
   unflagged rows are done.

The workbook ships with a few rows of sample data so you can see the shape it
expects and watch the Schedule work before you paste anything real. Delete them.

## Design notes

**Nothing volatile.** Column positions are resolved once with `MATCH`, and the
address ranges are built as `INDEX(...):INDEX(...)` rather than `INDIRECT(...)`.
Both resize when you change the row counts on Setup, but neither forces Excel to
recalculate the entire workbook on every keystroke — which `INDIRECT` does, and
which makes a sheet this shape unusable at real DFN sizes.

**Pre-2007 functions only** — `INDEX`, `MATCH`, `SUMPRODUCT`, `COUNTBLANK`,
`IFERROR`. No `XLOOKUP`, no dynamic arrays, so it runs on older Excel installs.

**Nearest address** is a full comparison of every splitter against every address,
via `SUMPRODUCT(MIN(...))` for the distance and a matching `MATCH` for the label.
Distances use a flat-earth approximation with longitude scaled by the cosine of
latitude, at 364,000 ft per degree — a mid-latitude WGS84 figure. That runs about
0.2% off a spherical-earth calculation, but the difference is a uniform scaling, so
it cannot change *which* address is nearest. On a reported distance of 500 ft it
works out to roughly a foot.

**Anything past the distance limit is left blank and flagged**, not filled in.
A splitter in open ground shouldn't get labelled with a house 900 ft away.

## Limits worth knowing before you rely on it

- **It needs an address layer.** No address points, nothing to match against.
  Reverse geocoding needs the Python script or an ArcGIS Notebook.
- **It's O(splitters × addresses).** A few hundred splitters against a few
  thousand addresses is fine. Tens of thousands of addresses will drag — set the
  last-row values on Setup to your real counts rather than leaving them high.
- **Pre-filled for 500 splitters.** More than that, select the last row of the
  Schedule tab and drag it down.
- **Export Data must be enabled** on the layer. It usually is for hosted feature
  layers; a referenced layer may not offer it.

## Rebuilding it

`DFN-Splitter-Matcher.xlsx` is generated, so it can be regenerated:

```bash
python3 build_template.py
```

Edit `build_template.py` rather than the workbook if you want to change the
formulas — otherwise your changes are lost the next time anyone rebuilds it.
