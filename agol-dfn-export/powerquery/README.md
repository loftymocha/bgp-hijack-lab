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
