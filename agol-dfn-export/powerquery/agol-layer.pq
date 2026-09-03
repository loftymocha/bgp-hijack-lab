// ---------------------------------------------------------------------------
// Pull an entire ArcGIS Online feature layer into Excel.
//
// Works when the layer's "Export Data" button is missing: exporting and
// querying are separate permissions, and this uses the query endpoint -- the
// same one the web map itself uses to draw the layer.
//
// Excel: Data > Get Data > From Other Sources > Blank Query > Advanced Editor.
// Delete everything in the editor, paste this in, edit the three values below.
// ---------------------------------------------------------------------------
let
    // ======== EDIT THESE ========

    // From the layer's item page, right-hand column, URL > Copy.
    // The number on the end identifies the layer and must be there.
    LayerUrl = "https://services9.arcgis.com/XXXXXXXX/arcgis/rest/services/YourService/FeatureServer/0",

    // Leave as "" first and try it. If you get a "Token Required" error,
    // see README.md in this folder for how to get one.
    Token = "",

    // "1=1" means every feature. Narrow it if you only want part of the layer,
    // e.g. "STATUS = 'AS_BUILT'".
    Where = "1=1",

    // ======== NOTHING BELOW HERE NEEDS EDITING ========

    // ArcGIS caps how many features it returns per request (commonly 1000 or
    // 2000), so a single call silently truncates a real DFN. This pages through
    // until a request comes back empty.
    PageSize = 1000,

    // Stops a runaway loop if the service ignores resultOffset -- an older
    // service without pagination support returns the same first page forever.
    // 100 pages at 1000 each is 100,000 features; raise it if you genuinely
    // have more, but first check the layer really is paging.
    MaxPages = 100,

    BaseQuery = [
        where = Where,
        outFields = "*",
        returnGeometry = "true",
        outSR = "4326",
        f = "json"
    ],

    GetPage = (offset as number) as list =>
        let
            Paged = BaseQuery & [
                resultOffset = Number.ToText(offset),
                resultRecordCount = Number.ToText(PageSize)
            ],
            WithAuth = if Token = "" then Paged else Paged & [token = Token],
            // RelativePath keeps this refreshable; a fully dynamic URL inside
            // Web.Contents trips Excel's "dynamic data source" refusal.
            Response = Json.Document(
                Web.Contents(LayerUrl, [RelativePath = "query", Query = WithAuth])
            ),
            Features =
                if Record.HasFields(Response, "features")
                then Response[features]
                else error Error.Record(
                    "ArcGIS error",
                    "The service returned no 'features'. Usually a bad URL or a missing token.",
                    Response
                )
        in
            Features,

    Pages = List.Generate(
        () => [Index = 0, Offset = 0, Batch = GetPage(0)],
        each List.Count(_[Batch]) > 0 and _[Index] < MaxPages,
        each [
            Index = _[Index] + 1,
            Offset = _[Offset] + PageSize,
            Batch = GetPage(_[Offset] + PageSize)
        ],
        each _[Batch]
    ),

    Features = List.Combine(Pages),

    AsTable = Table.FromList(Features, Splitter.SplitByNothing(), {"Feature"}),
    Parts = Table.ExpandRecordColumn(
        AsTable, "Feature", {"attributes", "geometry"}, {"attributes", "geometry"}
    ),

    // Field names come from the data itself, so this works on any layer
    // without being told the schema.
    FieldNames =
        if Table.RowCount(Parts) = 0
        then {}
        else Record.FieldNames(Parts{0}[attributes]),

    Attributes = Table.ExpandRecordColumn(Parts, "attributes", FieldNames, FieldNames),

    // Point layers carry x/y. On a line or polygon layer these come back null,
    // which is harmless -- delete the two columns if you don't want them.
    WithXY = Table.ExpandRecordColumn(Attributes, "geometry", {"x", "y"}, {"x", "y"})
in
    WithXY
