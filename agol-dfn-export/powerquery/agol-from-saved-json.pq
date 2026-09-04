// ---------------------------------------------------------------------------
// Load an ArcGIS layer into Excel from JSON you saved out of the browser.
//
// Use this when you can't get a token: your signed-in browser can already query
// the layer, so it does the fetching and Excel reads the result off disk.
// Nothing here touches the network, so there is no token to be refused.
//
// Point it at a FOLDER, not a single file. Every .json in there whose name
// starts with your prefix gets loaded and stacked into one table -- so a layer
// that needed several pages is just several files, no editing here.
//
//   dfn\splitters-1.json  \
//   dfn\splitters-2.json   >  Prefix = "splitters"  ->  one table
//   dfn\splitters-3.json  /
//   dfn\addresses-1.json      Prefix = "addresses"  ->  a separate query
//
// Excel: Data > Get Data > From Other Sources > Blank Query > Advanced Editor.
// Delete everything in the editor, paste this in, edit the two values below.
// ---------------------------------------------------------------------------
let
    // ======== EDIT THESE TWO ========

    // The folder holding your saved .json files. Backslashes are fine as-is.
    FolderPath = "C:\Users\YOURNAME\Desktop\dfn",

    // Loads every .json file whose name starts with this. Case doesn't matter.
    // Run this query once per layer, changing only this line.
    Prefix = "splitters",

    // ======== NOTHING BELOW HERE NEEDS EDITING ========

    Source = Folder.Files(FolderPath),
    Wanted = Table.SelectRows(
        Source,
        each Text.EndsWith(Text.Lower([Name]), ".json")
            and Text.StartsWith(Text.Lower([Name]), Text.Lower(Prefix))
    ),

    // Fail loudly rather than returning a confusing empty table.
    Checked =
        if Table.RowCount(Wanted) = 0 then
            error Error.Record(
                "No files matched",
                "Nothing in " & FolderPath & " both starts with """ & Prefix
                    & """ and ends in .json. Check the folder path and the file names.",
                null
            )
        else Wanted,

    WithFeatures = Table.AddColumn(Checked, "Feats", each
        let
            Doc = Json.Document([Content])
        in
            if Record.HasFields(Doc, "features") then Doc[features]
            else if Record.HasFields(Doc, "error") then
                error Error.Record(
                    "ArcGIS returned an error, not data",
                    [Name] & " holds an error response. Re-run that page in the browser and save it again.",
                    Doc[error]
                )
            else
                error Error.Record(
                    "Not an ArcGIS query result",
                    "No 'features' in " & [Name] & ". Check you saved the JSON output of the Query "
                        & "operation, not the layer's description page.",
                    null
                )
    ),

    Features = List.Combine(WithFeatures[Feats]),

    AsTable = Table.FromList(Features, Splitter.SplitByNothing(), {"Feature"}),
    Parts = Table.ExpandRecordColumn(
        AsTable, "Feature", {"attributes", "geometry"}, {"attributes", "geometry"}
    ),

    // Field names come from the data, so this works on any layer without being
    // told the schema.
    FieldNames =
        if Table.RowCount(Parts) = 0
        then {}
        else Record.FieldNames(Parts{0}[attributes]),

    Attributes = Table.ExpandRecordColumn(Parts, "attributes", FieldNames, FieldNames),

    // Point layers carry x/y, which is what the workbook needs. On line or
    // polygon layers these come back null; delete the columns if unwanted.
    WithXY = Table.ExpandRecordColumn(Attributes, "geometry", {"x", "y"}, {"x", "y"}),

    // Paging can overlap if an offset gets repeated; drop exact duplicates.
    Deduped = Table.Distinct(WithXY)
in
    Deduped
