"use strict";

/*
 * Structural table editing core (#121): tables survive an editor round-trip.
 *
 * The editor edits flat text, but table blocks are structured rows. This
 * module keeps both worlds honest: splitEditableContent flattens every
 * non-table block to text and leaves one inert marker ("[[table-N]]") where
 * each table stood; mergeEditableContent parses the edited text back into
 * blocks and swaps each marker for the (possibly re-edited) table block in
 * order. Deleting a marker deletes its table; duplicating a marker inserts
 * the table once (first occurrence wins). Everything is pure and mirrors
 * dqFormula's flatten/parse round-trip for math and text.
 */

(function (global) {
  const MARKER_RE = /\[\[table-(\d+)\]\]/g;

  function markerFor(index) {
    return `[[table-${index + 1}]]`;
  }

  function splitEditableContent(content) {
    const blocks = content && Array.isArray(content.blocks) ? content.blocks : [];
    const tables = [];
    const parts = [];
    for (const block of blocks) {
      let chunk = "";
      if (block.type === "line_break") chunk = "\n";
      else if (block.type === "math") {
        chunk = globalThis.dqFormula.formulaSource(
          block.latex || "", Boolean(block.metadata?.display)
        );
      } else if (block.type === "table") {
        chunk = markerFor(tables.length);
        tables.push(JSON.parse(JSON.stringify(block)));
      } else chunk = block.text || block.latex || block.alt_text || "";
      const previous = parts[parts.length - 1] ?? "";
      if (block.type === "math" && /\$$/.test(previous) && chunk.startsWith("$")) parts.push(" ");
      parts.push(chunk);
    }
    return { text: parts.join(""), tables };
  }

  function mergeEditableContent(text, tables, language = "en") {
    const source = String(text ?? "");
    const parsed = globalThis.dqFormula.parseEditableBlocks(source, language);
    const parsedBlocks = Array.isArray(parsed) ? parsed : parsed.blocks || [];
    const seen = new Set();
    const blocks = [];
    for (const block of parsedBlocks) {
      if (block.type !== "text" || !MARKER_RE.test(block.text)) {
        MARKER_RE.lastIndex = 0;
        blocks.push(block);
        continue;
      }
      MARKER_RE.lastIndex = 0;
      const textValue = block.text;
      let cursor = 0;
      for (const match of textValue.matchAll(MARKER_RE)) {
        const plain = textValue.slice(cursor, match.index);
        if (plain) blocks.push({ type: "text", text: plain, language });
        const index = Number(match[1]) - 1;
        if (Number.isInteger(index) && index >= 0 && index < tables.length && !seen.has(index)) {
          seen.add(index);
          blocks.push(tables[index]);
        }
        cursor = match.index + match[0].length;
      }
      const tail = textValue.slice(cursor);
      if (tail) blocks.push({ type: "text", text: tail, language });
    }
    return { blocks };
  }

  global.dqTableEdit = {
    MARKER_RE,
    markerFor,
    splitEditableContent,
    mergeEditableContent,
  };
})(globalThis);
