"use strict";

/*
 * Focused logic tests for structural table editing (#121):
 * - splitEditableContent flattens non-table blocks and leaves ordered
 *   markers where tables stood (math spacing preserved);
 * - mergeEditableContent round-trips content with tables intact;
 * - editing text around a marker keeps the table at its position;
 * - deleting a marker drops that table; duplicated markers insert once;
 * - cells edited through the merge carry the new values;
 * - content without tables is unchanged by a split->merge round-trip.
 */

const assert = require("node:assert/strict");
const path = require("node:path");

const WEB = path.resolve(__dirname, "..", "..", "src", "dq_questionbank_local", "web");
require(path.join(WEB, "formula.js"));
require(path.join(WEB, "table_edit.js"));
const dq = globalThis.dqTableEdit;

function testSplitLeavesMarkers() {
  const split = dq.splitEditableContent({
    blocks: [
      { type: "text", text: "Read the table.", language: "en" },
      { type: "table", rows: [["a", "b"], ["1", "2"]], metadata: { header_rows: 1 } },
      { type: "text", text: "Then answer.", language: "en" },
    ],
  });
  assert.equal(split.text, "Read the table.[[table-1]]Then answer.");
  assert.equal(split.tables.length, 1);
  assert.deepEqual(split.tables[0].rows, [["a", "b"], ["1", "2"]]);
}

function testRoundTripKeepsTablesIntact() {
  const content = {
    blocks: [
      { type: "text", text: "Before ", language: "en" },
      { type: "math", latex: "x+1", metadata: {} },
      { type: "table", rows: [["h"], ["v"]], metadata: { header_rows: 1, caption: "cap" } },
      { type: "text", text: " after", language: "en" },
    ],
  };
  const split = dq.splitEditableContent(content);
  const merged = dq.mergeEditableContent(split.text, split.tables, "en");
  const table = merged.blocks.find((block) => block.type === "table");
  assert.ok(table, "the table block survives the round-trip");
  assert.deepEqual(table.rows, [["h"], ["v"]]);
  assert.equal(table.metadata.caption, "cap");
  assert.equal(table.metadata.header_rows, 1);
  assert.ok(merged.blocks.some((block) => block.type === "math" && block.latex === "x+1"));
}

function testEditedCellsCarryThrough() {
  const split = dq.splitEditableContent({
    blocks: [{ type: "table", rows: [["old"]], metadata: {} }],
  });
  const edited = [{ type: "table", rows: [["new value"]], metadata: {} }];
  const merged = dq.mergeEditableContent(split.text, edited, "en");
  assert.equal(merged.blocks[0].rows[0][0], "new value");
}

function testMarkerDeletionDropsTheTable() {
  const split = dq.splitEditableContent({
    blocks: [
      { type: "table", rows: [["x"]], metadata: {} },
      { type: "text", text: "tail", language: "en" },
    ],
  });
  const merged = dq.mergeEditableContent("only tail", split.tables, "en");
  assert.equal(merged.blocks.filter((block) => block.type === "table").length, 0);
}

function testDuplicatedMarkerInsertsOnce() {
  const tables = [{ type: "table", rows: [["x"]], metadata: {} }];
  const merged = dq.mergeEditableContent(
    "[[table-1]] twice [[table-1]] end", tables, "en"
  );
  assert.equal(merged.blocks.filter((block) => block.type === "table").length, 1);
}

function testPlainContentRoundTrips() {
  const content = { blocks: [{ type: "text", text: "no tables $x$ here", language: "en" }] };
  const split = dq.splitEditableContent(content);
  assert.equal(split.tables.length, 0);
  const merged = dq.mergeEditableContent(split.text, [], "en");
  assert.equal(merged.blocks.filter((block) => block.type === "table").length, 0);
  assert.ok(merged.blocks.some((block) => block.type === "math"));
  assert.equal(
    merged.blocks.filter((block) => block.type === "text").map((block) => block.text).join(""),
    "no tables  here"
  );
}

function testTableWithoutTableEditStillFlattens() {
  const split = dq.splitEditableContent({
    blocks: [
      { type: "table", rows: [["a", "b"]], metadata: {} },
    ],
  });
  assert.match(split.text, /\[\[table-1\]\]/);
}

function main() {
  testSplitLeavesMarkers();
  testRoundTripKeepsTablesIntact();
  testEditedCellsCarryThrough();
  testMarkerDeletionDropsTheTable();
  testDuplicatedMarkerInsertsOnce();
  testPlainContentRoundTrips();
  testTableWithoutTableEditStillFlattens();
  console.log("table-edit checks passed");
}

main();
