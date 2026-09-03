# AGOL → Excel export for DFN splitter testing

Pulls every layer out of an ArcGIS Online web map and writes it to a formatted
Excel workbook. The point of it is the first sheet: a **splitter schedule** with
the tier label (Primary / Secondary / Tertiary) and the nearest street address
already filled in for each splitter — the part you're doing by hand today.

It talks to the plain ArcGIS REST endpoints, so it needs nothing but Python and
three pip packages. No ArcGIS Pro, no ArcGIS Python API, no conda.

---

## What comes out

| Sheet | Contents |
|---|---|
| **Index** | Every layer exported, with feature counts and links to its sheet |
| **Splitters** | One row per splitter: name, tier, ratio, nearest address, distance, lat/lon, QA flags |
| One per layer | Full attribute dump, coded domains decoded, dates readable, lon/lat appended |

Rows on the Splitters sheet that need a human get shaded and flagged: `no tier`,
`no address`, `address >500 ft`, `no ratio`, `duplicate name`, `no geometry`.
That flag column is the whole review list for a DFN — everything else is done.

Every sheet gets a frozen header row, an autofilter, and sized columns, so it's
sortable and filterable the moment it opens.

---

## Install

```bash
pip install -r requirements.txt
```

If pip is blocked on your work laptop, `pip install --user requests openpyxl pyyaml`
usually gets through; behind a corporate proxy add `--proxy http://your.proxy:8080`.

---

## Use it in three steps

### 1. Find out what's in your map

Copy `config.example.yaml` to `config.yaml` and put your web map id in it. The id
is the last part of the map's URL:

```
https://myorg.maps.arcgis.com/home/webmap/viewer.html?webmap=a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6
                                                              ^^^^^^^^^^ this ^^^^^^^^^^
```

Then:

```bash
python3 dfn_export.py -c config.yaml discover
```

This prints every layer in the map with its real field names, types, and which
fields carry coded domains. You need those exact names for the next step — the
field holding your tier is probably called something like `SPLTR_LEVEL` or
`SPLITTER_TYPE`, and it won't be spelled the way the map's popup spells it.

### 2. See what values those fields actually hold

```bash
python3 dfn_export.py -c config.yaml profile
```

Prints the distinct values in each field of your splitter layer, with counts:

```
SPLTR_LEVEL: Level 1 (34), Level 2 (112), Level 3 (486)
SPLIT_RATIO: 1x32 (486), 1x16 (112), 1x8 (34)
```

Now fill in `splitters.tier.keywords` in the config with those real values.

### 3. Export

```bash
python3 dfn_export.py -c config.yaml export -o "DFN-1234.xlsx"
```

---

## Configuring the tier label

Three ways to resolve it, tried in this order — the first that produces an answer wins:

1. **A field value.** `tier.fields` lists the fields to look at, `tier.keywords`
   maps their values onto the three tiers. Matching is case-insensitive and
   whole-word, so `"1"` matches a value of `1` or `Level 1` but not `1x16`.
2. **The split ratio.** If your build is consistent (say every primary is a 1x4),
   fill in `tier.ratio_map` and it fills the gaps where the tier field is empty.
3. **A naming pattern.** `tier.name_patterns` maps a regex against any attribute
   onto a tier — useful when the tier is only encoded in the splitter's name.

Anything still unresolved comes out blank and flagged `no tier`. It never guesses
silently — a blank you can see beats a wrong label you can't.

## Configuring the address

`address.source` has three settings:

- **`layer`** (default, recommended) — nearest point from an address layer that's
  already in your map. Free, instant, and it gives you the addresses your own
  organization considers authoritative. Set `address.layer` to a substring of the
  layer's title and `address.fields` to the fields that make up the address text.
  Anything farther than `max_distance_ft` is flagged rather than filled in, so a
  splitter in the middle of a field doesn't get labeled with a house 900 ft away.
- **`geocode`** — reverse geocode against the ArcGIS World Geocoder. Use this if
  there's no address layer in the map. **This spends ArcGIS credits** (roughly 40
  per 1,000 lookups). Results are cached in `geocode_cache.json` so a re-run of the
  same DFN costs nothing.
- **`none`** — leave the column blank.

---

## Other things worth knowing

**Filtering to as-builts.** `query.where` takes any SQL the service accepts, e.g.
`"STATUS = 'AS_BUILT'"`. It applies to every layer, so leave it at `1=1` if your
layers don't share the field.

**Skipping noise.** `query.skip_layers` drops layers whose title contains any of
the listed substrings. `query.only_layers` does the opposite when you want just one.

**Feature services without a map.** Put URLs in `source.service_urls` instead of
(or alongside) a web map id. A URL ending in `/FeatureServer` pulls every sublayer.

**CSVs too.** Set `output.csv_dir` to a folder and you get one CSV per layer next
to the workbook.

**Large layers.** Paging is automatic and handles services that cap at 1,000 or
2,000 records. `query.max_features_per_layer` is a safety stop, not a target.

---

## Testing it without a map

```bash
python3 test_dfn_export.py
```

Runs a full export against a fake in-memory ArcGIS service and checks the
workbook that comes out — domain decoding, tier classification, nearest-address
matching, QA flagging, sort order, and paging. Useful for confirming your Python
environment is sound before you point it at real credentials.

---

## No-install option: the Excel workbook

If you can't install Python — locked-down laptop, or you'd simply rather not run
scripts on a work machine — use **[`excel-template/DFN-Splitter-Matcher.xlsx`](excel-template/)**
instead. It does the tier labelling and nearest-address matching with Excel
formulas alone. You export two layers out of AGOL with its built-in
**Export Data → Export to CSV**, paste them in, and read the finished schedule.

It handles two layers rather than the whole map and can't reverse geocode, but it
removes the same manual step and needs nothing installed. See
[`excel-template/README.md`](excel-template/README.md).

## Also no-install: Excel Power Query

Excel can also hit the REST endpoint directly, which gets you a live, refreshable
table of a single layer that updates when the data does. It does no tier or address
work — for that use the workbook above — but it's the only option here that stays
connected to the live service.

**Data → Get Data → From Other Sources → Blank Query → Advanced Editor**, then:

```m
let
    Url = "https://services9.arcgis.com/YOURORG/arcgis/rest/services/DFN/FeatureServer/0/query",
    Source = Json.Document(
        Web.Contents(Url, [Query=[
            where="1=1", outFields="*", returnGeometry="false",
            resultRecordCount="2000", f="json"
        ]])
    ),
    Features = Table.FromList(Source[features], Splitter.SplitByNothing(), {"Column1"}),
    Attrs = Table.ExpandRecordColumn(Features, "Column1", {"attributes"}, {"attributes"}),
    Fields = Record.FieldNames(Attrs{0}[attributes]),
    Result = Table.ExpandRecordColumn(Attrs, "attributes", Fields, Fields)
in
    Result
```

Swap in your own layer URL — copy it from the layer's item page in AGOL, under
the **URL** button on the right. Refresh pulls current data. Note the 2,000-record
cap: Power Query won't page for you, which is most of why the script exists.

---

## Troubleshooting

| Message | Cause |
|---|---|
| `Sign-in failed` | Org accounts using SSO can't use username/password here — set `auth.mode: api_key` and generate a key in AGOL under Content → My content → New item → Developer credentials |
| `skipping 'X' (no service URL)` | A sketch/notes layer stored inside the map itself. There's nothing to query; expected |
| `no splitter rows` | `splitters.layers` doesn't match your layer's title. Run `discover` and copy the title |
| `no address` on every row | `address.layer` or `address.fields` don't match. Run `discover` on the address layer |
| `Token Required` / error 499 | The map or a layer isn't shared with your account, or the token expired mid-run (they last 4 hours) |
