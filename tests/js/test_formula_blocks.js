"use strict";

/*
 * Focused JavaScript tests for the Editor Center formula-block workflow.
 * They cover insert, edit, boundary preservation, canonical round-trip,
 * and the non-destructive malformed-source path from issue #19.
 */

const assert = require("node:assert/strict");

const dqFormula = require("../../src/dq_questionbank_local/web/formula.js");

let checks = 0;

function check(name, run) {
  run();
  checks += 1;
  console.log(`ok - ${name}`);
}

// Insert: a new formula lands at the caret with padded delimiters.
check("insert into an empty field", () => {
  const result = dqFormula.insertFormula("", 0, "x + 1", false);
  assert.equal(result.text, "$x + 1$");
  assert.equal(result.start, 0);
  assert.equal(result.end, 7);
});

check("insert pads glued neighbours", () => {
  const result = dqFormula.insertFormula("plain text", 5, "a+b", false);
  assert.equal(result.text, "plain $a+b$ text");
  assert.equal(result.start, 6);
  assert.equal(result.end, 11);
});

check("insert avoids double padding at edges", () => {
  assert.equal(dqFormula.insertFormula("hi", 0, "x", true).text, "$$x$$ hi");
  assert.equal(dqFormula.insertFormula("hi", 2, "x", true).text, "hi $$x$$");
  assert.equal(dqFormula.insertFormula("a b", 1, "x", false).text, "a $x$ b");
  assert.equal(dqFormula.insertFormula("a  b", 2, "x", false).text, "a $x$ b");
});

// Edit: the caret inside a delimited formula opens that exact block.
check("find formula range at the caret", () => {
  const range = dqFormula.findFormulaRange("ok $$x+1$$ ok", 7);
  assert.deepEqual(range, { start: 3, end: 10, latex: "x+1", display: true });
  assert.equal(dqFormula.findFormulaRange("no formula here", 4), null);
});

check("edit keeps surrounding text and boundaries", () => {
  const text = "before $x$ middle $$y$$ after";
  const range = dqFormula.findFormulaRange(text, 7);
  const result = dqFormula.replaceRange(text, range.start, range.end, "x^2 + 1", false);
  assert.equal(result.text, "before $x^2 + 1$ middle $$y$$ after");
  const other = dqFormula.findFormulaRange(result.text, 26);
  assert.deepEqual(other, { start: 24, end: 29, latex: "y", display: true });
});

check("switching between inline and display keeps neighbours intact", () => {
  const text = "a $x$ b";
  const range = dqFormula.findFormulaRange(text, 3);
  const toDisplay = dqFormula.replaceRange(text, range.start, range.end, range.latex, true);
  assert.equal(toDisplay.text, "a $$x$$ b");
  const back = dqFormula.replaceRange(toDisplay.text, toDisplay.start, toDisplay.end, "x", false);
  assert.equal(back.text, "a $x$ b");
});

// Preview/save path: canonical JSON stays distinguishable for inline and
// display math, and unchanged math blocks survive a nearby text edit.
check("flatten keeps display delimiters", () => {
  const content = {
    blocks: [
      { type: "text", text: "Derive " },
      { type: "math", latex: "x^2", metadata: { display: true } },
      { type: "text", text: " then " },
      { type: "math", latex: "y", metadata: {} },
    ],
  };
  assert.equal(dqFormula.flattenContent(content), "Derive $$x^2$$ then $y$");
});

check("adjacent math blocks stay parsable", () => {
  const flattened = dqFormula.flattenContent({
    blocks: [
      { type: "math", latex: "a", metadata: {} },
      { type: "math", latex: "b", metadata: { display: true } },
    ],
  });
  const reparsed = dqFormula.parseEditableBlocks(flattened);
  const summary = reparsed.blocks.map((block) => [
    block.type,
    block.latex,
    Boolean(block.metadata?.display),
  ]);
  assert.deepEqual(summary, [
    ["math", "a", false],
    ["text", undefined, false],
    ["math", "b", true],
  ]);
});

check("blocks round-trip without flattening math", () => {
  const original = {
    blocks: [
      { type: "text", text: "Solve ", language: "en" },
      { type: "math", latex: "\\frac{1}{2}", language: "en", metadata: {} },
      { type: "text", text: " and ", language: "en" },
      { type: "math", latex: "x^2 = 4", language: "en", metadata: { display: true } },
      { type: "text", text: ".", language: "en" },
    ],
  };
  const roundTrip = dqFormula.parseEditableBlocks(dqFormula.flattenContent(original));
  assert.deepEqual(roundTrip, original);
});

check("nearby text edit preserves unchanged math blocks", () => {
  const content = {
    blocks: [
      { type: "text", text: "Solve ", language: "en" },
      { type: "math", latex: "x + 1", language: "en", metadata: { display: true } },
      { type: "text", text: " now.", language: "en" },
    ],
  };
  const flattened = dqFormula.flattenContent(content);
  const edited = flattened.replace("Solve", "Please solve");
  const reparsed = dqFormula.parseEditableBlocks(edited);
  assert.deepEqual(
    reparsed.blocks.filter((block) => block.type === "math"),
    [{ type: "math", latex: "x + 1", language: "en", metadata: { display: true } }],
  );
});

check("inline and display blocks stay distinguishable in canonical JSON", () => {
  const blocks = dqFormula.parseEditableBlocks("$a$ $$b$$").blocks.filter((block) => block.type === "math");
  assert.deepEqual(blocks[0].metadata, {});
  assert.deepEqual(blocks[1].metadata, { display: true });
});

// Malformed input: the source is never erased or silently rewritten.
check("malformed latex keeps its raw source", () => {
  const tokens = dqFormula.parseDelimitedText("check $\\frac{1}{$ end");
  const math = tokens.find((token) => token.type === "math");
  assert.equal(math.raw, "$\\frac{1}{$");
  assert.equal(math.latex, "\\frac{1}{");
});

check("unclosed delimiter stays plain text", () => {
  const blocks = dqFormula.parseEditableBlocks("price \\$5 and $x").blocks;
  assert.equal(blocks.length, 1);
  assert.equal(blocks[0].type, "text");
  assert.equal(blocks[0].text, "price \\$5 and $x");
});

check("empty formula delimiters are ignored", () => {
  const blocks = dqFormula.parseEditableBlocks("a $$ $$ b").blocks;
  assert.deepEqual(blocks, [{ type: "text", text: "a $$ $$ b", language: "en" }]);
});

console.log(`${checks} formula checks passed`);
