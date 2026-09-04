# Reading an AGOL layer when Export Data is missing

If the **Export Data** button isn't on the layer's item page, the layer's owner
hasn't enabled the export capability (or it's a referenced service, or your role
lacks the privilege). You can't turn that on yourself.

It doesn't matter. **Exporting and querying are separate permissions.** The
`/query` endpoint is what the web map uses to draw the layer every time you pan,
so if you can see the layer, you can read it. `agol-layer.pq` does exactly that,
and pages through the whole layer instead of stopping at the service's
per-request cap.

## Use it

1. **Get the layer URL.** Item page → right-hand column → **URL** → **Copy**.
   It ends in a number (`.../FeatureServer/0`) that identifies which layer in
   the service you want. That number matters — `/0` and `/3` are different layers.
2. In Excel: **Data → Get Data → From Other Sources → Blank Query**
3. **Home → Advanced Editor**, select everything already in there, delete it,
   and paste in the contents of `agol-layer.pq`
4. Edit `LayerUrl` at the top. Leave `Token` as `""` on the first attempt.
5. **Done → Close & Load**

Repeat for your address layer into a second query.

## Is the layer public, or does it need a token?

Quick test, before you fight with Excel: copy the layer URL, add this to the end,
and open it in a **private / incognito** browser window.

```
/query?where=1%3D1&outFields=*&resultRecordCount=1&f=json
```

- **JSON comes back** → the layer is public. Leave `Token = ""` and you're done.
- **It demands a sign-in, or returns `"code":499`** → you need a token below.

Use a private window specifically because your normal window is already signed
in and will succeed either way, which tells you nothing. Excel doesn't share
your browser's session.

## If you can't get a token at all

An AGOL account without developer privileges has no way to mint one: there is no
token UI, and `generateToken` is a POST endpoint, not a page you can visit and
fill in. If that's you, don't fight it — use **`agol-from-saved-json.pq`** instead.

The trick is that your signed-in browser can already query the layer. So let it:

1. On the layer's **ArcGIS REST Services Directory** page, scroll to the bottom
   and click **Query** under Supported Operations.
2. Set `Where` to `1=1`, `Out Fields` to `*`, `Return Geometry` to `true`,
   `Output Spatial Reference` to `4326`, `Format` to `JSON`. Run it.
3. Save the JSON to a file.
4. Point `agol-from-saved-json.pq` at the folder, with a filename prefix per layer.

No credentials anywhere, because nothing but the browser touches the network.
The cost is that it's a snapshot rather than a live connection — a new DFN means
exporting again.

**Filter at the source.** If the layer covers more than you need, narrow it in the
form's `Where` box — plain SQL, no URL encoding: `STATE = 'WA'`. Every feature
excluded is one fewer to page through. To find what values a field actually
holds (`WA` vs `Washington` vs `53` — guessing wrong returns zero features, not
an error), ask the layer:

```
/query?where=1%3D1&outFields=STATE&returnDistinctValues=true&f=json
```

With no usable attribute, filter by area instead — append a bounding box and
leave `where` as `1=1`:

```
&geometry=-124.85,45.54,-116.91,49.00&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects
```

(That envelope is Washington state. A box is a rectangle, so it also catches
edges of Oregon, Idaho and BC.)

**Page from the address bar, not the form.** Once a query works, copy its URL and
change only `resultOffset` for each page — far quicker than re-filling the form:

```
/query?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&resultRecordCount=2000&resultOffset=0&f=json
```

**Watch the feature count.** The service caps a single query, so a result of
exactly 1,000 or 2,000 features means there's more. Set **Result Offset** to that
number, run again, and save as a second file in the same folder. The loader
stacks every file matching the prefix, so nothing in the query needs changing.
Repeat until a run comes back short; overlapping pages are deduplicated.

## Getting a token

Two options, in order of preference.

**An API key** (long-lived, revocable, can be read-only). In AGOL: **Content →
My content → New item → Developer credentials → API key**. Scope it to reading
this layer, generate it, paste it into `Token`. Best option because it isn't
your password, it can't write anything, and you can revoke it on its own.
Requires privileges to create content — if that menu isn't there, use the next one.

**A short-lived token.** Visit:

```
https://<yourorg>.maps.arcgis.com/sharing/rest/generateToken
```

You get an Esri-hosted form. Enter your username and password, set **Referer**
to `https://www.arcgis.com`, set an expiration, and it returns a token string.
Paste that into `Token`.

This one expires — when the refresh starts failing with a 499, generate another.
That friction is the reason the API key is worth chasing first.

> A token is a credential. It belongs in this query on your own machine and
> nowhere else — not in an email, not in a shared workbook, not in a ticket.
> If a workbook containing one gets shared, revoke it.

## Known limits

- **Paging cap.** `MaxPages` stops at 100,000 features, which also protects
  against an old service that ignores `resultOffset` and would otherwise return
  page one forever. Raise it only after confirming the layer really pages.
- **Coded domains come back as raw codes.** The query endpoint returns the
  stored value, so a tier field may arrive as `1`/`2`/`3` rather than
  `Level 1`/`Level 2`/`Level 3`. That's fine — the Excel template's tier lookup
  maps whatever values you actually get. Just enter the codes.
- **Dates arrive as epoch milliseconds.** To convert in Power Query: add a
  custom column with `#datetime(1970,1,1,0,0,0) + #duration(0,0,0,[YourField]/1000)`.
- **Geometry** is expanded to `x`/`y`, which is what you want for splitters and
  address points. On line or polygon layers those columns come back null.
