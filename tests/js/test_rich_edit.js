"use strict";

/*
 * Focused logic tests for rich formula editing (#93 slices 1-2 + move core):
 * - empty {} slots project to one visible placeholder, with exact
 *   source<->projection offset maps and escaped-brace immunity;
 * - Tab navigation finds the next/previous slot, wrapping never happens;
 * - repairCaret restores a stable caret across projection re-renders;
 * - moveMathBlock reorders formula blocks while text stays in place;
 * - the DOM host syncs edits back to LaTeX and selects slots on Tab.
 */

const assert = require("node:assert/strict");
const path = require("node:path");

const WEB = path.resolve(__dirname, "..", "..", "src", "dq_questionbank_local", "web");
require(path.join(WEB, "formula.js"));
require(path.join(WEB, "rich_edit.js"));
const dq = globalThis.dqRichEdit;

function testFindEmptySlots() {
  assert.deepEqual(
    dq.findEmptySlots("x^{2} + {} - {}"),
    [{ start: 8, end: 10 }, { start: 13, end: 15 }]
  );
  assert.deepEqual(dq.findEmptySlots("\\{\\} literal"), [], "escaped braces are not slots");
  assert.deepEqual(dq.findEmptySlots("no slots"), []);
}

function testProjectionRoundTrip() {
  const projection = dq.projectForEditing("a + {} = {}");
  assert.equal(projection.text, `a + ${dq.PLACEHOLDER} = ${dq.PLACEHOLDER}`);
  assert.equal(dq.sourceFromProjection(projection.text), "a + {} = {}");
  const plain = dq.projectForEditing("x + 1");
  assert.equal(plain.text, "x + 1");
  assert.equal(plain.slots.length, 0);
}

function testOffsetMaps() {
  const projection = dq.projectForEditing("\\frac{}{2} + {}");
  const source = "\\frac{}{2} + {}";
  for (let offset = 0; offset <= projection.text.length; offset += 1) {
    const sourceOffset = dq.sourceOffsetFromProjection(projection, offset);
    assert.ok(sourceOffset >= 0 && sourceOffset <= source.length, "map stays in range");
    const back = dq.projectionOffsetFromSource(projection, sourceOffset);
    assert.equal(back, offset, "projection->source->projection is the identity");
  }
}

function testSlotNavigation() {
  const text = `a ${dq.PLACEHOLDER} b ${dq.PLACEHOLDER} c`;
  assert.equal(dq.nextSlotOffset(text, 0), 2);
  assert.equal(dq.nextSlotOffset(text, 2), 2, "caret on the slot selects that slot");
  assert.equal(dq.nextSlotOffset(text, 3), 6);
  assert.equal(dq.nextSlotOffset(text, 7), null, "no slot after the last one");
  assert.equal(dq.previousSlotOffset(text, 99), 6);
  assert.equal(dq.previousSlotOffset(text, 6), 2);
  assert.equal(dq.previousSlotOffset(text, 2), null, "no slot before the first one");
  assert.equal(dq.nextSlotOffset("plain", 0), null);
}

function testRepairCaret() {
  assert.equal(dq.repairCaret("abcdef", 3, "abcdef"), 3, "unchanged text keeps the caret");
  assert.equal(dq.repairCaret("abcdef", 6, "abcde"), 5, "clamps to the shorter text");
  assert.equal(dq.repairCaret("abcdef", 3, "abcXYZf"), 3, "prefix match anchors the caret");
  assert.equal(dq.repairCaret("ab{}cd", 4, "ab{}"), 4, "suffix match anchors the caret");
  assert.equal(dq.repairCaret("", 0, "abc"), 0);
}

function testMoveMathBlock() {
  assert.equal(dq.moveMathBlock("a $x$ b $y$ c", 0, 1), "a $y$ b $x$ c");
  assert.equal(dq.moveMathBlock("a $x$ b $y$ c", 1, -1), "a $y$ b $x$ c");
  assert.equal(dq.moveMathBlock("$x$ then $y$", 0, -1), "$x$ then $y$", "clamped move is a no-op");
  assert.equal(dq.moveMathBlock("plain text only", 0, 1), "plain text only");
  assert.equal(dq.moveMathBlock("no math at all", 5, 2), "no math at all", "bad index is a no-op");
}



function stubHost() {
  return {
    listeners: {},
    attributes: {},
    hidden: false,
    focused: false,
    classList: {
      classes: new Set(),
      add(name) { this.classes.add(name); },
      remove(name) { this.classes.delete(name); },
    },
    setAttribute(name, value) { this.attributes[name] = value; },
    addEventListener(type, handler) {
      this.listeners[type] = this.listeners[type] || [];
      this.listeners[type].push(handler);
    },
    removeEventListener(type, handler) {
      this.listeners[type] = (this.listeners[type] || []).filter((item) => item !== handler);
    },
    dispatch(type, event) {
      for (const handler of [...(this.listeners[type] || [])]) handler(event);
    },
    focus() { this.focused = true; },
  };
}

function makeEnvironment() {
  const host = stubHost();
  let text = "";
  let caret = 0;
  Object.defineProperty(host, "textContent", {
    get() { return text; },
    set(value) { text = String(value); },
  });
  Object.defineProperty(host, "firstChild", {
    get() { return text ? host : null; },
  });
  const persistent = {
    endContainer: null,
    endOffset: 0,
    cloneRange() { return this; },
    selectNodeContents() {},
    setStart(node, offset) { caret = offset; },
    setEnd(node, offset) { caret = offset; },
    toString() { return text.slice(0, caret); },
  };
  const selectionStub = {
    rangeCount: 1,
    removeAllRanges() {},
    addRange(range) {
      persistent.endContainer = range.__node ?? null;
      persistent.endOffset = range.__end ?? 0;
    },
    getRangeAt() { return persistent; },
  };
  global.document = {
    createRange: () => ({
      __node: null,
      __end: 0,
      selectNodeContents() {},
      collapse() {},
      setStart(node, offset) {
        this.__node = node;
        this.__end = offset;
        caret = offset;
      },
      setEnd(node, offset) {
        this.__node = node;
        this.__end = offset;
        caret = offset;
      },
    }),
  };
  global.window = { getSelection: () => selectionStub };
  return { host, getCaret: () => caret };
}

function withDomHost(run) {
  const savedDocument = global.document;
  const savedWindow = global.window;
  const environment = makeEnvironment();
  try {
    run(environment);
  } finally {
    global.document = savedDocument;
    global.window = savedWindow;
  }
}

function testHostSyncsEditsBackToLatex() {
  withDomHost(({ host }) => {
    let latest = null;
    const editor = dq.createRichFormulaEditor(host, {
      getLatex: () => "\\frac{}{2}",
      onChange: (latex) => { latest = latex; },
    });
    assert.equal(host.textContent, `\\frac${dq.PLACEHOLDER}{2}`);
    host.dispatch("input", {});
    assert.equal(latest, "\\frac{}{2}");
    editor.destroy();
    assert.equal(host.listeners.input.length, 0, "destroy removes handlers");
  });
}

function testHostTabSelectsTheNextSlot() {
  withDomHost(({ host, getCaret }) => {
    const editor = dq.createRichFormulaEditor(host, {
      getLatex: () => "{} + {}",
      onChange: () => {},
    });
    let prevented = false;
    host.dispatch("keydown", {
      key: "Tab",
      shiftKey: false,
      preventDefault() { prevented = true; },
    });
    assert.ok(prevented, "Tab default is suppressed");
    const firstSlot = host.textContent.indexOf(dq.PLACEHOLDER);
    assert.equal(
      getCaret(),
      firstSlot + 1,
      "the slot placeholder is selected, so the next keystroke fills it"
    );
    editor.destroy();
  });
}

function testHostRefreshRepairsTheCaret() {
  withDomHost(({ host, getCaret }) => {
    let latex = "";
    const editor = dq.createRichFormulaEditor(host, {
      getLatex: () => latex,
      onChange: () => {},
    });
    assert.equal(host.textContent, "");
    latex = "abc{}def";
    editor.refresh();
    assert.equal(host.textContent, `abc${dq.PLACEHOLDER}def`);
    assert.ok(getCaret() <= host.textContent.length, "caret stays in range after refresh");
    editor.destroy();
  });
}

function main() {
  testFindEmptySlots();
  testProjectionRoundTrip();
  testOffsetMaps();
  testSlotNavigation();
  testRepairCaret();
  testMoveMathBlock();
  testHostSyncsEditsBackToLatex();
  testHostTabSelectsTheNextSlot();
  testHostRefreshRepairsTheCaret();
  console.log("rich-edit checks passed");
}

main();
