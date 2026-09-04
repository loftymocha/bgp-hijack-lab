// ---------------------------------------------------------------------------
// Load an ArcGIS layer into Excel from JSON you saved out of the browser.
//
// Use this when you can't get a token: your signed-in browser can already query
// the layer, so let it do the fetching and hand Excel the result as a file.
// Nothing here touches the network, so there is no token and no permission to
// be refused.
//
// Excel: Data > Get Data > From Other Sources > Blank Query > Advanced Editor.
// Delete everything in the editor, paste this in, edit the file list below.
// ---------------------------------------------------------------------------
let
    // ======== EDIT THIS ========

    // Full paths to the .json files you saved from the REST Query form.
    // One file is usually enough. Add more only if the layer needed paging --
    // the runbook explains how to tell.
    //
    // Backslashes are fine as-is. Keep each path in quotes, commas between them.
    Files = {
        "C:\Users\YOURNAME\Desktop\splitters.json"
        // , "C:\Users\YOURNAME\Desktop\splitters-2.json"
    },

    // ======== NOTHING BELOW HERE NEEDS EDITING ========

    LoadOne = (path as text) as list =>
        let
            Doc = Json.Document(File.Contents(path)),
            Features =
                if Record.HasFields(Doc, "features") then Doc[features]
                else if Record.HasFields(Doc, "error") then
                    error Error.Record(
                        "ArcGIS returned an error, not data",
                        "Re-run the query in the browser and save the result again.",
                        Doc[error]
                    )
                else
                    error Error.Record(
                        "Not an ArcGIS query result",
                        "No 'features' in " & path & ". Check you saved the JSON output of the "
                            & "Query operation, not the layer's description page.",
                        null
                    )
        in
            Features,

    Features = List.Combine(List.Transform(Files, LoadOne)),

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
    WithXY = Table.ExpandRecordColumn(Attributes, "geometry", {"x", "y"}, {"x", "y"})
in
    WithXY
