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
4. Fill in the tier lookup. Each rule is matched **exactly first, then as a word
   inside the value**. So `Primary` matches `Primary 1x128` — three rules cover a
   text layer however many ratio combinations exist — while a subtype code of `7`
   matches only the rule `7`, never `17` or `70`. Both sides are compared as
   text, so the number `7` and the text `"7"` are the same value.

   The third column, **Ratio**, is for when the value carries no readable ratio.
   A subtype code of `7` tells you nothing, but its name was `Primary 1x128`, so
   type `1x128` beside that rule and the schedule fills it in.
5. Read the `Schedule` tab. Filter the **QA Flags** column: flagged rows need you,
   unflagged rows are done.

The workbook ships with a few rows of sample data so you can see the shape it
expects and watch the Schedule work before you paste anything real. Delete them.

## When the ratio is part of the device name

Fiber schemas often carry no separate ratio field, because the ratio is already
in the device type: `Primary 1x128`, `Secondary 1x16`.

Three sources are tried, in order:

1. **The Ratio column beside the matched rule on Setup** — the only option that
   works for subtype codes, where the stored value is a bare integer.
2. **A ratio field named on Setup**, where it has a value.
3. **Extracted from the tier value itself** — `1x<n>` lifted out of
   `Primary 1x128`.

A layer whose type field is a **subtype** (its `Type ID Field` on the directory
page) stores integers, not names. Read the code-to-name pairs from the layer's
**Types** section and fill one lookup row per subtype: code, tier, ratio.

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

## Verifying it

Two checks, both offline:

```bash
python3 verify_math.py      # the arithmetic is right
python3 verify_formulas.py  # Excel will actually compute it (pip install formulas)
```

`verify_math.py` reimplements the Schedule tab's logic independently and checks
tier mapping, nearest-address selection, and the distance gate. `verify_formulas.py`
evaluates the workbook's real formulas and confirms every one parses, resolves,
and lands on the expected value rather than `#REF!`/`#VALUE!`/`#N/A`.

The second builds a scaled-down variant first — same formulas, smaller lookup
bound — because the formula engine materialises those grids in memory and the
shipped 100,000-row bound exhausts it. Excel itself has no such problem.

## Rebuilding it

`DFN-Splitter-Matcher.xlsx` is generated, so it can be regenerated:

```bash
python3 build_template.py
```

Edit `build_template.py` rather than the workbook if you want to change the
formulas — otherwise your changes are lost the next time anyone rebuilds it.
